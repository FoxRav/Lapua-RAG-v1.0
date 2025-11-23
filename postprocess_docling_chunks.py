"""
Docling-postiprosessori: normalisoi ja rikastaa chunkit RAG:ia varten.

Tämä skripti:
1. Normalisoi chunkit selkeään skeemaan
2. Suodattaa taulukot pois pääindeksistä
3. Poimii metatiedot (organisaatio, päivämäärä, pykälä)
4. Deduplikoi toistuvat muutoksenhakuohjeet
5. Luo lopullisen RAG-indeksiformaatin
"""

import hashlib
import json
import logging
import os
import re
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

# Konfiguroi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
_log = logging.getLogger(__name__)


# Organisaatiotunnisteet
ORGANISAATIOT = [
    "Kaupunginhallitus",
    "Kaupunginvaltuusto",
    "Hyvinvointilautakunta",
    "Teknisen lautakunta",
    "Koululautakunta",
    "Lautakunta",
    "Valtuusto",
    "Hallitus",
]

# Section-tyypit patternien perusteella
SECTION_PATTERNS = {
    "paatos": [
        r"päätös",
        r"päätetään",
        r"päätöksellä",
    ],
    "perustelut": [
        r"perustelut",
        r"perustelu",
    ],
    "muutoksenhaku": [
        r"muutoksenhaku",
        r"oikaisuvaatimus",
        r"valitus",
        r"muutoksenhakua",
    ],
    "talous": [
        r"talousarvio",
        r"budjetti",
        r"toteuma",
        r"rahoitus",
    ],
}


def normalize_for_hash(text: str) -> str:
    """
    Normalisoi teksti hash-laskentaa varten.

    Args:
        text: Alkuperäinen teksti

    Returns:
        Normalisoitu teksti
    """
    return text.lower().replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()


def calculate_hash(text: str) -> str:
    """
    Laske SHA1-hash normalisoidusta tekstistä.

    Args:
        text: Teksti

    Returns:
        SHA1-hash hex-muodossa
    """
    normalized = normalize_for_hash(text)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def extract_organisation(text: str, file_path: str) -> str | None:
    """
    Poimi organisaatio tekstistä tai tiedostopolusta.

    Args:
        text: Chunkin teksti
        file_path: Tiedostopolku

    Returns:
        Organisaation nimi tai None
    """
    # Tarkista ensin tiedostopolku
    path_lower = file_path.lower()
    for org in ORGANISAATIOT:
        if org.lower() in path_lower:
            return org

    # Tarkista tekstistä (ensimmäiset 500 merkkiä)
    text_sample = text[:500].lower()
    for org in ORGANISAATIOT:
        if org.lower() in text_sample:
            return org

    return None


def parse_date_from_filename(path: str) -> datetime | None:
    """
    Poimi päivämäärä tiedostonimestä.

    Args:
        path: Tiedostopolku

    Returns:
        datetime-objekti tai None
    """
    # Etsi päivämäärä tiedostonimestä (esim. "Pöytäkirja-Kaupunginvaltuusto - 02.06.2025, klo 17_00.pdf")
    match = re.search(r"(\d{2}\.\d{2}\.\d{4})", path)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%d.%m.%Y")
    except ValueError:
        return None


def is_plausible_year(date_obj: datetime | None) -> bool:
    """
    Tarkista onko päivämäärä järkevä.

    Args:
        date_obj: datetime-objekti

    Returns:
        True jos vuosi on 2000-2035 välillä
    """
    if date_obj is None:
        return False
    return 2000 <= date_obj.year <= 2035


def extract_date(text: str, file_path: str) -> str | None:
    """
    Poimi päivämäärä tiedostonimestä (ensisijaisesti) tai tekstistä (backup).

    Args:
        text: Chunkin teksti
        file_path: Tiedostopolku

    Returns:
        Päivämäärä YYYY-MM-DD -muodossa tai None
    """
    # 1. Ensisijaisesti: tiedostonimi
    file_date = parse_date_from_filename(file_path)
    if is_plausible_year(file_date):
        return file_date.strftime("%Y-%m-%d")

    # 2. Backup: etsi päivämäärä tekstistä (dd.mm.yyyy)
    date_patterns = [
        r"(\d{1,2})\.(\d{1,2})\.(\d{4})",  # 10.11.2025
        r"(\d{4})-(\d{1,2})-(\d{1,2})",  # 2025-11-10
    ]

    text_sample = text[:1000]  # Tarkista ensimmäiset 1000 merkkiä

    for pattern in date_patterns:
        match = re.search(pattern, text_sample)
        if match:
            if len(match.groups()) == 3:
                d, m, y = match.groups()
                try:
                    year_int = int(y)
                    # Tarkista että vuosi on järkevä
                    if 2000 <= year_int <= 2035:
                        date_obj = datetime(year_int, int(m), int(d))
                        if is_plausible_year(date_obj):
                            return date_obj.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    continue

    # 3. Jos ei löydy, palauta None (EI 1123-01-01 -placeholderia)
    return None


def extract_section(text: str) -> str | None:
    """
    Poimi pykälä tekstistä.

    Args:
        text: Chunkin teksti

    Returns:
        Pykälä (esim. "§ 81") tai None
    """
    # Etsi §-merkki
    section_patterns = [
        r"§\s*(\d+)",
        r"pykälä\s+(\d+)",
        r"pyk\.\s*(\d+)",
    ]

    text_sample = text[:500]  # Tarkista ensimmäiset 500 merkkiä

    for pattern in section_patterns:
        match = re.search(pattern, text_sample, re.IGNORECASE)
        if match:
            return f"§ {match.group(1)}"

    return None


def detect_section_type(text: str) -> str:
    """
    Päättele section-tyyppi tekstin perusteella.

    Args:
        text: Chunkin teksti

    Returns:
        Section-tyyppi: "paatos", "perustelut", "muutoksenhaku", "talous", "muu"
    """
    text_lower = text.lower()

    # Tarkista patternit järjestyksessä
    for section_type, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return section_type

    return "muu"


def is_table_chunk(chunk: dict[str, Any]) -> bool:
    """
    Tarkista onko chunk taulukko.

    Args:
        chunk: Chunk-dict

    Returns:
        True jos chunk on taulukko
    """
    # Tarkista doc_items-metadata
    if "metadata" in chunk:
        metadata = chunk["metadata"]
        if "doc_items" in metadata:
            for item in metadata["doc_items"]:
                if isinstance(item, dict) and item.get("label") == "table":
                    return True
                if hasattr(item, "label") and str(item.label) == "table":
                    return True

    # Tarkista myös tekstistä (taulukot sisältävät usein | merkkejä)
    text = chunk.get("text", "") or chunk.get("contextualized_text", "")
    if "|" in text and text.count("|") > 5:
        # Voi olla markdown-taulukko
        lines = text.split("\n")
        if len([l for l in lines if "|" in l]) > 3:
            return True

    return False


def estimate_tokens(text: str) -> int:
    """
    Arvioi tokenien määrä tekstistä (nopea arvio: ~4 merkkiä per token).

    Args:
        text: Teksti

    Returns:
        Arvioitu tokenien määrä
    """
    return len(text) // 4


def normalize_chunk(
    chunk: dict[str, Any],
    document_index: int,
    source_file: str,
    seen_hashes: set[str],
    min_tokens: int = 150,
    max_tokens: int = 512,
) -> dict[str, Any] | None:
    """
    Normalisoi yksi chunk lopulliseen skeemaan.

    Args:
        chunk: Alkuperäinen chunk Doclingista
        document_index: Dokumentin indeksi
        source_file: Lähdetiedoston polku
        seen_hashes: Set nähtyjä hasheja deduplikaatiota varten

    Returns:
        Normalisoitu chunk tai None jos se pitää jättää pois
    """
    # Hae teksti (käytä contextualized_textiä)
    text = chunk.get("contextualized_text") or chunk.get("text", "")

    if not text or len(text.strip()) < 10:
        return None  # Liian lyhyt chunk

    # Tarkista tokenien määrä
    estimated_tokens = estimate_tokens(text)

    # Filtteröi liian lyhyet chunkit (mikrochunkit <30 tokenia)
    if estimated_tokens < 30:
        # Poikkeus: jos on hyvin lyhyt mutta selkeä kokonaisuus (esim. yksi päätöslause)
        # Tarkista onko se päätös tai pykälä
        text_lower = text.lower()
        is_short_decision = (
            "päätetään" in text_lower
            or "päätös" in text_lower
            or text_lower.startswith("§")
        )
        if not is_short_decision:
            # Merkitse liian lyhyeksi (yhdistetään myöhemmin)
            pass  # Jätetään normalisoinnin jälkeen yhdistettäväksi

    # Varoita jos chunk on liian pitkä (pitäisi olla harvinaista max_tokens=512:n kanssa)
    if estimated_tokens > max_tokens * 1.2:  # 20% toleranssi
        _log.warning(
            f"Chunk on pidempi kuin max_tokens: ~{estimated_tokens} tokenia "
            f"(max: {max_tokens})"
        )

    # Laske hash deduplikaatiota varten
    text_hash = calculate_hash(text)

    # Deduplikaatio: jos hash on jo nähty, jätä pois
    if text_hash in seen_hashes:
        return None

    seen_hashes.add(text_hash)

    # Poimi metatiedot
    source_path = Path(source_file)
    source_relative = str(source_path.relative_to(source_path.parent.parent.parent)) if source_path.exists() else source_file

    organisaatio = extract_organisation(text, source_file)
    
    # Poimi päivämäärä (tiedostonimi ensin, sitten teksti)
    kokous_pvm = extract_date(text, source_file)
    
    # Korjauspassi: jos päivämäärä on 1123, yritä uudestaan
    if kokous_pvm and kokous_pvm.startswith("1123-"):
        # Yritä uudestaan: ensin tiedostonimi, sitten tekstipvm; jos ei onnistu -> None
        file_date = parse_date_from_filename(source_file)
        if is_plausible_year(file_date):
            kokous_pvm = file_date.strftime("%Y-%m-%d")
        else:
            # Yritä tekstistä uudestaan
            text_date_str = extract_date(text, "")  # Älä käytä tiedostopolkua tässä
            if text_date_str and not text_date_str.startswith("1123-"):
                kokous_pvm = text_date_str
            else:
                kokous_pvm = None
    
    pykala = extract_section(text)
    section_type = detect_section_type(text)

    # Rakenna lopullinen chunk
    final_chunk = {
        "id": f"doc_{document_index}_chunk_{chunk.get('chunk_id', 0)}",
        "text": text,  # contextualized_text menee embeddingiin
        "source_file": source_relative,
        "organisaatio": organisaatio,
        "kokous_pvm": kokous_pvm,
        "pykala": pykala,
        "chunk_index": chunk.get("chunk_id", 0),
        "total_chunks": chunk.get("metadata", {}).get("total_chunks_in_document", 0),
        "section_type": section_type,
        "is_table": False,
        "hash": text_hash,
    }

    return final_chunk


def merge_small_chunks(
    chunks: list[dict[str, Any]],
    min_tokens: int = 30,
    target_tokens: int = 384,
) -> list[dict[str, Any]]:
    """
    Yhdistä liian lyhyet chunkit seuraavaan chunkkiin.

    Args:
        chunks: Lista normalisoituja chunkkeja
        min_tokens: Vähimmäiskoko ennen yhdistämistä
        target_tokens: Tavoitekoko

    Returns:
        Yhdistetty lista chunkkeja
    """
    if not chunks:
        return []

    merged = []
    i = 0

    while i < len(chunks):
        current = chunks[i].copy()
        current_tokens = estimate_tokens(current.get("text", ""))

        # Jos chunk on liian lyhyt, yritä yhdistää seuraavaan
        if current_tokens < min_tokens and i + 1 < len(chunks):
            next_chunk = chunks[i + 1]

            # Yhdistä vain jos:
            # 1. Molemmat ovat samasta dokumentista
            # 2. Sama organisaatio
            # 3. Sama section_type (tai toinen on "muu")
            # 4. Yhdistetty koko ei ylitä target_tokens * 1.5
            if (
                current.get("source_file") == next_chunk.get("source_file")
                and current.get("organisaatio") == next_chunk.get("organisaatio")
            ):
                # Tarkista section_type-yhteensopivuus
                current_section = current.get("section_type", "muu")
                next_section = next_chunk.get("section_type", "muu")
                sections_compatible = (
                    current_section == next_section
                    or current_section == "muu"
                    or next_section == "muu"
                )

                if sections_compatible:
                    combined_text = current.get("text", "") + "\n\n" + next_chunk.get("text", "")
                    combined_tokens = estimate_tokens(combined_text)

                    if combined_tokens <= target_tokens * 1.5:
                        # Yhdistä chunkit
                        current["text"] = combined_text
                        current["chunk_index"] = min(
                            current.get("chunk_index", 0),
                            next_chunk.get("chunk_index", 0),
                        )
                        # Yhdistä pykälät jos saatavilla
                        if not current.get("pykala") and next_chunk.get("pykala"):
                            current["pykala"] = next_chunk.get("pykala")
                        # Päivitä hash
                        current["hash"] = calculate_hash(combined_text)
                        i += 1  # Ohita seuraava chunk (se on nyt yhdistetty)
                    else:
                        # Liian suuri yhdistettynä, jätä nykyinen sellaisenaan
                        pass
            # Jos eivät täytä ehtoja, jätä nykyinen sellaisenaan

        merged.append(current)
        i += 1

    return merged


def process_combined_dataset(
    input_json: str | Path,
    output_json: str | Path,
    output_jsonl: str | Path | None = None,
    min_tokens: int = 150,
    max_tokens: int = 512,
    merge_small: bool = True,
    target_tokens: int = 384,
) -> dict[str, Any]:
    """
    Prosessoi yhdistetyn Docling-datasetin ja normalisoi chunkit.

    Args:
        input_json: Polku combined_chunks_only.json -tiedostoon
        output_json: Polku output JSON-tiedostoon
        output_jsonl: Polku output JSONL-tiedostoon (valinnainen)

    Returns:
        Yhteenveto prosessoinnista
    """
    input_path = Path(input_json)
    if not input_path.exists():
        raise FileNotFoundError(f"Input-tiedostoa ei löydy: {input_path}")

    _log.info(f"Ladataan dataset: {input_path}")
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = data.get("chunks", [])
    _log.info(f"Löydetty {len(chunks)} chunkkia")

    # Prosessoi chunkit
    final_chunks = []
    seen_hashes: set[str] = set()
    hash_counts: dict[str, int] = {}  # Laske hashien esiintymät deduplikaation debug:ia varten
    tables: list[dict[str, Any]] = []  # Tallenna taulukot erilliseen tiedostoon
    tables_count = 0
    duplicates_count = 0
    processed_count = 0
    too_short_count = 0

    _log.info("Aloitetaan normalisointi...")

    for i, chunk in enumerate(chunks):
        if (i + 1) % 1000 == 0:
            _log.info(f"Prosessoitu {i + 1}/{len(chunks)} chunkkia...")

        # Hae lähdetiedosto
        source_file = chunk.get("metadata", {}).get("source_file", "")
        document_index = chunk.get("metadata", {}).get("document_index", 0)

        # Tarkista onko taulukko
        if is_table_chunk(chunk):
            # Tallenna taulukko erilliseen listaan
            table_data = {
                "source_file": source_file,
                "text": chunk.get("contextualized_text") or chunk.get("text", ""),
                "organisaatio": extract_organisation(
                    chunk.get("contextualized_text") or chunk.get("text", ""), source_file
                ),
                "kokous_pvm": extract_date(
                    chunk.get("contextualized_text") or chunk.get("text", ""), source_file
                ),
            }
            tables.append(table_data)
            tables_count += 1
            continue

        # Laske hash deduplikaation debug:ia varten (ennen normalisointia)
        chunk_text = chunk.get("contextualized_text") or chunk.get("text", "")
        if chunk_text:
            text_hash = calculate_hash(chunk_text)
            hash_counts[text_hash] = hash_counts.get(text_hash, 0) + 1

        # Normalisoi chunk
        normalized = normalize_chunk(
            chunk, document_index, source_file, seen_hashes, min_tokens, max_tokens
        )

        if normalized is None:
            # Tarkista miksi jätettiin pois
            duplicates_count += 1
            continue

        # Tarkista onko liian lyhyt (yhdistetään myöhemmin)
        if estimate_tokens(normalized.get("text", "")) < 30:
            too_short_count += 1

        final_chunks.append(normalized)
        processed_count += 1

    _log.info(f"\n{'='*60}")
    _log.info("NORMALISOINTI VALMIS!")
    _log.info(f"{'='*60}")
    # Laske token-tilastot
    token_stats = [estimate_tokens(c.get("text", "")) for c in final_chunks]
    avg_tokens = sum(token_stats) / len(token_stats) if token_stats else 0

    _log.info(f"Alkuperäisiä chunkkeja: {len(chunks)}")
    _log.info(f"Normalisoituja chunkkeja: {len(final_chunks)}")
    _log.info(f"Taulukoita tallennettu: {tables_count}")
    _log.info(f"Duplikaatteja jätetty pois: {duplicates_count}")
    _log.info(f"Liian lyhyitä chunkkeja (<30 tokenia): {too_short_count}")

    # Yhdistä liian lyhyet chunkit
    if merge_small:
        _log.info(f"\nYhdistetään liian lyhyet chunkit (<{min_tokens} tokenia)...")
        before_merge = len(final_chunks)
        final_chunks = merge_small_chunks(final_chunks, min_tokens, target_tokens)
        after_merge = len(final_chunks)
        _log.info(f"Yhdistetty: {before_merge} → {after_merge} chunkkia")

    # Laske token-tilastot
    token_stats = [estimate_tokens(c.get("text", "")) for c in final_chunks]
    avg_tokens = sum(token_stats) / len(token_stats) if token_stats else 0

    _log.info(f"\nKeskimääräinen chunk-koko: ~{avg_tokens:.0f} tokenia")
    _log.info(f"Chunk-koko vaihteluväli: {min(token_stats) if token_stats else 0} - {max(token_stats) if token_stats else 0} tokenia")
    _log.info(f"Tavoite: ~{target_tokens} tokenia")
    
    # Laske kuinka monta chunkkia on tavoite-alueella
    target_range = [
        c for c in final_chunks
        if target_tokens * 0.7 <= estimate_tokens(c.get("text", "")) <= max_tokens
    ]
    _log.info(f"Chunkkeja tavoite-alueella ({int(target_tokens * 0.7)}-{max_tokens} tokenia): {len(target_range)}/{len(final_chunks)} ({len(target_range)/len(final_chunks)*100:.1f}%)")
    
    _log.info(f"{'='*60}\n")

    # Deduplikaation debug-logit
    _log.info("Deduplikaation debug-tilastot:")
    top_hashes = sorted(hash_counts.items(), key=lambda x: -x[1])[:10]
    _log.info(f"Top-10 hashit (eniten esiintymiä):")
    for i, (hash_val, count) in enumerate(top_hashes, 1):
        if count > 1:  # Näytä vain duplikaatit
            # Etsi esimerkkiteksti tälle hashille
            example_text = None
            for chunk in chunks:
                chunk_text = chunk.get("contextualized_text") or chunk.get("text", "")
                if calculate_hash(chunk_text) == hash_val:
                    example_text = chunk_text[:200]  # Ensimmäiset 200 merkkiä
                    break
            _log.info(
                f"  {i}. Hash {hash_val[:16]}...: {count} esiintymää"
            )
            if example_text:
                _log.info(f"     Esimerkki: {example_text}...")

    _log.info(f"{'='*60}\n")

    # Tallenna taulukot erilliseen tiedostoon
    if tables:
        tables_path = Path(output_json).parent / "tables_normalized.jsonl"
        _log.info(f"Tallennetaan taulukot: {tables_path}")
        with tables_path.open("w", encoding="utf-8") as f:
            for table in tables:
                f.write(json.dumps(table, ensure_ascii=False) + "\n")
        _log.info(f"✅ Taulukot tallennettu: {len(tables)} taulukkoa")

    # Tallenna JSON
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Laske token-tilastot
    token_stats = []
    for chunk in final_chunks:
        tokens = estimate_tokens(chunk.get("text", ""))
        token_stats.append(tokens)

    avg_tokens = sum(token_stats) / len(token_stats) if token_stats else 0
    min_actual = min(token_stats) if token_stats else 0
    max_actual = max(token_stats) if token_stats else 0

    output_data = {
        "metadata": {
            "total_original_chunks": len(chunks),
            "total_normalized_chunks": len(final_chunks),
            "tables_saved": tables_count,
            "duplicates_filtered": duplicates_count,
            "too_short_before_merge": too_short_count,
            "processing_date": data.get("metadata", {}).get("processing_date", ""),
            "chunk_size_stats": {
                "avg_tokens": round(avg_tokens, 1),
                "min_tokens": min_actual,
                "max_tokens": max_actual,
                "target_tokens": 384,
                "max_tokens_limit": max_tokens,
            },
        },
        "chunks": final_chunks,
    }

    _log.info(f"Tallennetaan JSON: {output_path}")
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # Tallenna myös JSONL (yksi chunk per rivi)
    if output_jsonl:
        jsonl_path = Path(output_jsonl)
        _log.info(f"Tallennetaan JSONL: {jsonl_path}")
        with jsonl_path.open("w", encoding="utf-8") as f:
            for chunk in final_chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    return output_data


def main():
    """Pääfunktio."""
    # Input ja output -tiedostot
    # Käytä ympäristömuuttujia tai komentoriviparametreja
    if len(sys.argv) > 1:
        base_dir = Path(sys.argv[1])
    else:
        # Oletus: 106PDF_output jos se on olemassa
        default_dir = Path("106PDF_output")
        if default_dir.exists():
            base_dir = default_dir
        else:
            base_dir = Path(os.getenv("LAPUA_RAG_OUTPUT_DIR", "."))
    
    input_json = base_dir / "combined_chunks_only.json"
    output_json = base_dir / "normalized_chunks.json"
    output_jsonl = base_dir / "normalized_chunks.jsonl"

    try:
        result = process_combined_dataset(
            input_json=input_json,
            output_json=output_json,
            output_jsonl=output_jsonl,
            min_tokens=30,  # Vähimmäiskoko ennen yhdistämistä (mikrochunkit)
            max_tokens=512,  # Maksimikoko (Lapua-RAG optimaalinen)
            merge_small=True,  # Yhdistä liian lyhyet chunkit
            target_tokens=384,  # Tavoitekoko
        )

        print(f"\n✅ Postiprosessointi valmis!")
        print(f"   - Normalisoituja chunkkeja: {len(result['chunks'])}")
        print(f"   - Taulukoita tallennettu: {result['metadata']['tables_saved']}")
        print(f"   - Duplikaatteja suodatettu: {result['metadata']['duplicates_filtered']}")
        print(f"   - Output: {output_json}")

    except Exception as e:
        _log.error(f"Virhe postiprosessoinnissa: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

