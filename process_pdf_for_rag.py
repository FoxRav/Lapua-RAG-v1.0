"""
Optimaalinen PDF-prosessointiskripti RAG-järjestelmää varten.

Tämä skripti:
- Prosessoi PDF:n parhaalla mahdollisella tavalla (OCR, layout, taulukot)
- Käyttää HybridChunkeria kontekstin säilyttämiseen
- Tallentaa metadataa (sivu, dokumentti, jne.)
- Viedään JSON ja Markdown muotoon
- On skaalautuva satoihin dokumentteihin

Asennus:
    pip install docling

Vaihtoehtoisesti, jos käytät embedding-mallia:
    pip install docling transformers
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

# Korjaa Windows-symlink-ongelma HuggingFace Hub:lle
# Estää symlinkkien käytön, mikä aiheuttaa ongelmia Windowsissa ilman Developer Modea
# Tämä täytyy asettaa ENNEN kuin HuggingFace Hub ladataan
# HUOM: Jos tämä ei toimi, aja PowerShellissa:
#   $env:HF_HUB_DISABLE_SYMLINKS = "1"
#   python process_pdf_for_rag.py
if "HF_HUB_DISABLE_SYMLINKS" not in os.environ:
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
if "HF_HUB_DISABLE_SYMLINKS_WARNING" not in os.environ:
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from docling.chunking import HybridChunker
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend

# Konfiguroi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
_log = logging.getLogger(__name__)


def process_pdf_for_rag(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
    embed_model_id: str | None = None,
) -> dict[str, Any]:
    """
    Prosessoi PDF-tiedoston RAG-järjestelmää varten.

    Args:
        pdf_path: Polku PDF-tiedostoon
        output_dir: Output-kansio (jos None, käytetään samaa kansiota kuin PDF)
        embed_model_id: Embedding-mallin ID (esim. "sentence-transformers/all-MiniLM-L6-v2")
                        Jos None, käytetään oletusasetuksia

    Returns:
        Dict joka sisältää chunkit, metadata ja dokumentin tiedot
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF-tiedostoa ei löydy: {pdf_path}")

    if output_dir is None:
        output_dir = pdf_path.parent / "rag_output"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    _log.info(f"Prosessoidaan PDF: {pdf_path.name}")

    # Konfiguroi optimaalinen PDF-pipeline RAG:ia varten
    # Oletusasetukset käyttävät automaattista OCR-valintaa ja taulukkorakenteen tunnistusta
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,  # OCR skannatuille PDF:ille
        do_table_structure=True,  # Taulukoiden rakenne
        # ocr_options ja table_structure_options käyttävät oletusarvoja
        # (OcrAutoOptions ja TableStructureOptions)
    )

    # Käytä parasta backendia (v4)
    pdf_format_option = PdfFormatOption(
        pipeline_options=pipeline_options,
        backend=DoclingParseV4DocumentBackend,
    )

    # Luo converter optimaalisilla asetuksilla
    converter = DocumentConverter(
        format_options={InputFormat.PDF: pdf_format_option}
    )

    # Prosessoi dokumentti
    _log.info("Aloitetaan dokumentin prosessointi...")
    result: ConversionResult = converter.convert(pdf_path)

    if result.status.value != "success":
        raise RuntimeError(
            f"Dokumentin prosessointi epäonnistui: {result.status.value}"
        )

    doc = result.document
    _log.info("Dokumentti prosessoitu onnistuneesti")

    # Alusta chunker
    if embed_model_id:
        from docling_core.transforms.chunker.tokenizer.huggingface import (
            HuggingFaceTokenizer,
        )
        from transformers import AutoTokenizer

        tokenizer = HuggingFaceTokenizer(
            tokenizer=AutoTokenizer.from_pretrained(embed_model_id),
        )
        chunker = HybridChunker(tokenizer=tokenizer)
        _log.info(f"Käytetään embedding-mallia: {embed_model_id}")
    else:
        chunker = HybridChunker()
        _log.info("Käytetään oletus-chunkeria")

    # Chunkkaa dokumentti
    _log.info("Aloitetaan chunking...")
    chunks = list(chunker.chunk(doc))
    _log.info(f"Luotu {len(chunks)} chunkkia")

    # Kerää chunkit metadataineen
    chunk_data = []
    for i, chunk in enumerate(chunks):
        # Kontekstualisoi chunk (lisää metadataa)
        contextualized_text = chunker.contextualize(chunk)

        chunk_info = {
            "chunk_id": i,
            "text": chunk.text,
            "contextualized_text": contextualized_text,
            "metadata": {
                "source_file": str(pdf_path),
                "source_name": pdf_path.name,
                "chunk_index": i,
                "total_chunks": len(chunks),
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

    # Valmistele output-data
    output_data = {
        "source_file": str(pdf_path),
        "source_name": pdf_path.name,
        "total_chunks": len(chunks),
        "chunks": chunk_data,
        "document_metadata": {
            "title": getattr(doc, "title", None),
            "pages": len(doc.pages) if hasattr(doc, "pages") else None,
        },
    }

    # Tallenna JSON
    json_output_path = output_dir / f"{pdf_path.stem}_rag.json"
    with json_output_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    _log.info(f"JSON tallennettu: {json_output_path}")

    # Tallenna myös Markdown (koko dokumentti)
    md_output_path = output_dir / f"{pdf_path.stem}_full.md"
    markdown_content = doc.export_to_markdown()
    with md_output_path.open("w", encoding="utf-8") as f:
        f.write(markdown_content)
    _log.info(f"Markdown tallennettu: {md_output_path}")

    # Tallenna chunkit erilliseen Markdown-tiedostoon
    chunks_md_path = output_dir / f"{pdf_path.stem}_chunks.md"
    with chunks_md_path.open("w", encoding="utf-8") as f:
        f.write(f"# Chunks for {pdf_path.name}\n\n")
        f.write(f"Total chunks: {len(chunks)}\n\n")
        f.write("---\n\n")
        for chunk_info in chunk_data:
            f.write(f"## Chunk {chunk_info['chunk_id']}\n\n")
            f.write(f"**Metadata:** {chunk_info['metadata']}\n\n")
            f.write(f"**Text:**\n{chunk_info['text']}\n\n")
            f.write("---\n\n")
    _log.info(f"Chunk-markdown tallennettu: {chunks_md_path}")

    # Tallenna myös DoclingDocument JSON (täysi rakenne)
    from docling_core.types.doc import ImageRefMode

    doc_json_path = output_dir / f"{pdf_path.stem}_docling.json"
    doc.save_as_json(doc_json_path, image_mode=ImageRefMode.PLACEHOLDER)
    _log.info(f"DoclingDocument JSON tallennettu: {doc_json_path}")

    _log.info(f"Prosessointi valmis! Output-kansio: {output_dir}")

    return output_data


def main():
    """Pääfunktio esimerkkiä varten."""
    # Käytä käyttäjän antamaa PDF-tiedostoa
    pdf_path = (
        r"F:\Projekti-Lapua\Projekti2-20251123\DATA_päättävät_elimet_20251123"
        r"\Kaupunginvaltuusto\2025\Pöytäkirja-Kaupunginvaltuusto - 10.11.2025, klo 17_14.pdf"
    )

    # Valinnainen: määritä embedding-malli jos käytät tiettyä mallia RAG:ssa
    # embed_model_id = "sentence-transformers/all-MiniLM-L6-v2"

    try:
        result = process_pdf_for_rag(
            pdf_path=pdf_path,
            embed_model_id=None,  # Käytä oletusta, tai määritä oma malli
        )
        print(f"\n✅ Prosessointi valmis!")
        print(f"   - Luotu {result['total_chunks']} chunkkia")
        print(f"   - Output-kansio: {Path(pdf_path).parent / 'rag_output'}")
    except Exception as e:
        _log.error(f"Virhe prosessoinnissa: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

