"""
Batch-prosessointiskripti kaikille dokumenteille RAG-järjestelmää varten.

Tämä skripti:
- Etsii kaikki PDF-dokumentit rekursiivisesti annetusta kansiosta
- Prosessoi ne kaikki optimaalisesti
- Yhdistää kaikki chunkit yhteen suureen JSON-tiedostoon
- Säilyttää metadataa lähdedokumenteista
- Luo myös yksittäiset tiedostot jokaiselle dokumentille
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# Korjaa Windows-symlink-ongelma HuggingFace Hub:lle
if "HF_HUB_DISABLE_SYMLINKS" not in os.environ:
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
if "HF_HUB_DISABLE_SYMLINKS_WARNING" not in os.environ:
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from docling.chunking import HybridChunker
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
from docling_core.types.doc import ImageRefMode

# Konfiguroi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
_log = logging.getLogger(__name__)


def find_all_pdfs(root_dir: str | Path) -> list[Path]:
    """
    Etsii kaikki PDF-tiedostot rekursiivisesti.

    Args:
        root_dir: Juurikansio josta etsitään

    Returns:
        Lista PDF-tiedostojen polkuja
    """
    root_dir = Path(root_dir)
    pdf_files = list(root_dir.rglob("*.pdf"))
    _log.info(f"Löydetty {len(pdf_files)} PDF-tiedostoa kansiosta: {root_dir}")
    return sorted(pdf_files)


def process_single_document(
    pdf_path: Path,
    converter: DocumentConverter,
    chunker: HybridChunker,
    output_dir: Path,
) -> dict[str, Any] | None:
    """
    Prosessoi yhden dokumentin ja palauttaa chunkit.

    Args:
        pdf_path: Polku PDF-tiedostoon
        converter: DocumentConverter-instanssi
        chunker: HybridChunker-instanssi
        output_dir: Output-kansio

    Returns:
        Dict chunkkeineen tai None jos prosessointi epäonnistui
    """
    try:
        _log.info(f"Prosessoidaan: {pdf_path.name}")

        # Prosessoi dokumentti
        result: ConversionResult = converter.convert(pdf_path)

        if result.status != ConversionStatus.SUCCESS:
            _log.warning(
                f"Dokumentti {pdf_path.name} prosessoitu osittain tai epäonnistui: "
                f"{result.status.value}"
            )
            if result.status == ConversionStatus.FAILURE:
                return None

        doc = result.document

        # Chunkkaa dokumentti
        chunks = list(chunker.chunk(doc))

        # Kerää chunkit metadataineen
        chunk_data = []
        for i, chunk in enumerate(chunks):
            contextualized_text = chunker.contextualize(chunk)

            chunk_info = {
                "chunk_id": i,
                "text": chunk.text,
                "contextualized_text": contextualized_text,
                "metadata": {
                    "source_file": str(pdf_path),
                    "source_name": pdf_path.name,
                    "source_relative_path": str(pdf_path.relative_to(pdf_path.parent.parent.parent)),
                    "chunk_index": i,
                    "total_chunks_in_document": len(chunks),
                },
            }

            # Lisää chunkin metadata jos saatavilla
            if hasattr(chunk, "meta") and chunk.meta:
                if hasattr(chunk.meta, "doc_items") and chunk.meta.doc_items:
                    chunk_info["metadata"]["doc_items"] = [
                        {
                            "label": str(item.label) if hasattr(item, "label") else None,
                            "page": getattr(item, "page", None),
                        }
                        for item in chunk.meta.doc_items
                    ]

            chunk_data.append(chunk_info)

        # Tallenna yksittäinen dokumentti (valinnainen)
        doc_output_dir = output_dir / "individual_documents" / pdf_path.stem
        doc_output_dir.mkdir(parents=True, exist_ok=True)

        # JSON chunkkeineen
        doc_json_path = doc_output_dir / f"{pdf_path.stem}_rag.json"
        doc_data = {
            "source_file": str(pdf_path),
            "source_name": pdf_path.name,
            "total_chunks": len(chunks),
            "chunks": chunk_data,
            "document_metadata": {
                "title": getattr(doc, "title", None),
                "pages": len(doc.pages) if hasattr(doc, "pages") else None,
            },
        }
        with doc_json_path.open("w", encoding="utf-8") as f:
            json.dump(doc_data, f, ensure_ascii=False, indent=2)

        # Markdown
        md_output_path = doc_output_dir / f"{pdf_path.stem}_full.md"
        markdown_content = doc.export_to_markdown()
        with md_output_path.open("w", encoding="utf-8") as f:
            f.write(markdown_content)

        _log.info(
            f"✅ {pdf_path.name}: {len(chunks)} chunkkia luotu "
            f"({result.status.value})"
        )

        return {
            "document": doc_data,
            "chunks": chunk_data,
            "status": result.status.value,
        }

    except Exception as e:
        _log.error(f"❌ Virhe prosessoinnissa {pdf_path.name}: {e}", exc_info=True)
        return None


def process_all_documents_for_rag(
    root_dir: str | Path,
    output_dir: str | Path | None = None,
    embed_model_id: str | None = None,
    max_tokens: int | None = None,
    save_individual: bool = True,
) -> dict[str, Any]:
    """
    Prosessoi kaikki PDF-dokumentit kansiosta ja yhdistää ne RAG:ia varten.

    Args:
        root_dir: Juurikansio josta etsitään PDF-tiedostot
        output_dir: Output-kansio (jos None, luodaan rag_output juurikansioon)
        embed_model_id: Embedding-mallin ID (esim. "sentence-transformers/all-MiniLM-L6-v2")
                        Jos None, käytetään oletustokenizeria
        max_tokens: Chunkkien maksimikoko tokenissa (esim. 512, 1024, 2048)
                    Jos None, käytetään tokenizerin oletusarvoa (~512)
                    Suuremmat arvot = suuremmat chunkit = vähemmän chunkkeja
        save_individual: Tallenna myös yksittäiset dokumentit

    Returns:
        Dict joka sisältää kaikki chunkit yhdistettynä
    """
    root_dir = Path(root_dir)
    if not root_dir.exists():
        raise FileNotFoundError(f"Kansiota ei löydy: {root_dir}")

    if output_dir is None:
        output_dir = root_dir / "106PDF_output"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    if save_individual:
        (output_dir / "individual_documents").mkdir(parents=True, exist_ok=True)

    _log.info(f"Aloitetaan batch-prosessointi: {root_dir}")
    _log.info(f"Output-kansio: {output_dir}")

    # Etsi kaikki PDF-tiedostot
    pdf_files = find_all_pdfs(root_dir)
    if not pdf_files:
        raise ValueError(f"Ei löydetty PDF-tiedostoja kansiosta: {root_dir}")

    # Konfiguroi converter
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
    )

    pdf_format_option = PdfFormatOption(
        pipeline_options=pipeline_options,
        backend=DoclingParseV4DocumentBackend,
    )

    converter = DocumentConverter(
        format_options={InputFormat.PDF: pdf_format_option}
    )

    # Alusta chunker
    if embed_model_id or max_tokens:
        from docling_core.transforms.chunker.tokenizer.huggingface import (
            HuggingFaceTokenizer,
        )
        from transformers import AutoTokenizer

        # Jos embed_model_id on määritelty, käytä sitä
        # Muuten käytä oletustokenizeria
        if embed_model_id:
            model_id = embed_model_id
            _log.info(f"Käytetään embedding-mallia: {embed_model_id}")
        else:
            # Oletustokenizer (sentence-transformers/all-MiniLM-L6-v2)
            model_id = "sentence-transformers/all-MiniLM-L6-v2"
            _log.info(f"Käytetään oletustokenizeria: {model_id}")

        tokenizer_obj = AutoTokenizer.from_pretrained(model_id)
        
        # Jos max_tokens on määritelty, käytä sitä
        # Muuten käytä tokenizerin oletusarvoa
        tokenizer_kwargs = {}
        if max_tokens is not None:
            tokenizer_kwargs["max_tokens"] = max_tokens
            _log.info(f"Chunkkien maksimikoko: {max_tokens} tokenia")
        else:
            default_max = getattr(tokenizer_obj, "model_max_length", 512)
            _log.info(f"Käytetään tokenizerin oletusarvoa: {default_max} tokenia")

        tokenizer = HuggingFaceTokenizer(
            tokenizer=tokenizer_obj,
            **tokenizer_kwargs,
        )
        chunker = HybridChunker(tokenizer=tokenizer)
    else:
        chunker = HybridChunker()
        _log.info("Käytetään oletus-chunkeria (oletusarvo ~512 tokenia)")

    # Prosessoi kaikki dokumentit
    all_chunks = []
    all_documents = []
    processed_count = 0
    failed_count = 0
    total_chunks = 0

    start_time = time.time()

    _log.info(f"\n{'='*60}")
    _log.info(f"Prosessoidaan {len(pdf_files)} dokumenttia...")
    _log.info(f"{'='*60}\n")

    for i, pdf_path in enumerate(pdf_files, 1):
        _log.info(f"[{i}/{len(pdf_files)}] {pdf_path.name}")

        result = process_single_document(pdf_path, converter, chunker, output_dir)

        if result:
            all_documents.append(result["document"])
            # Lisää dokumentin chunkit globaaliin listaan
            for chunk in result["chunks"]:
                # Lisää globaali chunk_id
                chunk["global_chunk_id"] = len(all_chunks)
                chunk["document_index"] = len(all_documents) - 1
                all_chunks.append(chunk)
                total_chunks += 1

            processed_count += 1
        else:
            failed_count += 1

        # Progress-indikaattori
        if i % 10 == 0 or i == len(pdf_files):
            elapsed = time.time() - start_time
            avg_time = elapsed / i
            remaining = (len(pdf_files) - i) * avg_time
            _log.info(
                f"Edistyminen: {i}/{len(pdf_files)} dokumenttia, "
                f"{processed_count} onnistui, {failed_count} epäonnistui. "
                f"Arvioitu aika jäljellä: {remaining/60:.1f} min"
            )

    elapsed_time = time.time() - start_time

    # Yhdistä kaikki chunkit yhteen tiedostoon
    _log.info(f"\n{'='*60}")
    _log.info("Yhdistetään kaikki chunkit yhteen tiedostoon...")
    _log.info(f"{'='*60}\n")

    combined_data = {
        "metadata": {
            "total_documents": len(pdf_files),
            "processed_documents": processed_count,
            "failed_documents": failed_count,
            "total_chunks": total_chunks,
            "processing_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "root_directory": str(root_dir),
        },
        "documents": all_documents,
        "all_chunks": all_chunks,
    }

    # Tallenna yhdistetty JSON
    combined_json_path = output_dir / "combined_rag_dataset.json"
    _log.info(f"Tallennetaan yhdistetty dataset: {combined_json_path}")
    with combined_json_path.open("w", encoding="utf-8") as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=2)
    _log.info(f"✅ Yhdistetty dataset tallennettu: {combined_json_path}")

    # Tallenna myös yksinkertaistettu versio (vain chunkit)
    chunks_only_path = output_dir / "combined_chunks_only.json"
    chunks_only_data = {
        "metadata": combined_data["metadata"],
        "chunks": all_chunks,
    }
    with chunks_only_path.open("w", encoding="utf-8") as f:
        json.dump(chunks_only_data, f, ensure_ascii=False, indent=2)
    _log.info(f"✅ Chunkit tallennettu: {chunks_only_path}")

    # Yhteenveto
    _log.info(f"\n{'='*60}")
    _log.info("PROSESSOINTI VALMIS!")
    _log.info(f"{'='*60}")
    _log.info(f"Käsitelty dokumentteja: {processed_count}/{len(pdf_files)}")
    _log.info(f"Epäonnistuneita: {failed_count}")
    _log.info(f"Yhteensä chunkkeja: {total_chunks}")
    _log.info(f"Kokonaisaika: {elapsed_time/60:.1f} minuuttia")
    _log.info(f"Keskimääräinen aika/dokumentti: {elapsed_time/len(pdf_files):.1f} sekuntia")
    _log.info(f"Output-kansio: {output_dir}")
    _log.info(f"{'='*60}\n")

    return combined_data


def main():
    """Pääfunktio."""
    # Käytä käyttäjän antamaa kansiota
    # Käytä ympäristömuuttujaa tai komentoriviparametria
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    else:
        root_dir = os.getenv("LAPUA_RAG_ROOT_DIR")
        if not root_dir:
            _log.error("Anna root-kansio komentoriviparametrina tai aseta LAPUA_RAG_ROOT_DIR")
            _log.info("Käyttö: python process_all_documents_for_rag.py <root_kansio>")
            return

    # Valinnainen: määritä embedding-malli jos käytät tiettyä mallia RAG:ssa
    # embed_model_id = "sentence-transformers/all-MiniLM-L6-v2"

    try:
        result = process_all_documents_for_rag(
            root_dir=root_dir,
            embed_model_id=None,  # Käytä oletusta, tai määritä oma malli
            max_tokens=512,  # Chunkkien maksimikoko tokenissa (Lapua-RAG optimaalinen: 384-512)
            save_individual=True,  # Tallenna myös yksittäiset dokumentit
        )

        print(f"\n✅ Prosessointi valmis!")
        print(f"   - Käsitelty dokumentteja: {result['metadata']['processed_documents']}")
        print(f"   - Yhteensä chunkkeja: {result['metadata']['total_chunks']}")
        print(f"   - Output-kansio: {Path(root_dir) / '106PDF_output'}")

    except Exception as e:
        _log.error(f"Virhe prosessoinnissa: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

