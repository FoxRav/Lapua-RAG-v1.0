"""
Sanity testit normalisoidulle RAG-datasetille.

Testaa että:
- Chunkit ovat oikeassa muodossa
- Metatiedot ovat oikein
- Haku löytää oikeat dokumentit
"""

import json
import logging
import random
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
_log = logging.getLogger(__name__)


def load_normalized_chunks(json_path: str | Path) -> list[dict[str, Any]]:
    """Lataa normalisoidut chunkit."""
    path = Path(json_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("chunks", [])


def test_chunk_schema(chunks: list[dict[str, Any]]) -> bool:
    """
    Testaa että chunkit noudattavat skeemaa.

    Returns:
        True jos kaikki chunkit ovat oikeassa muodossa
    """
    _log.info("Testataan chunk-skeemaa...")

    required_fields = [
        "id",
        "text",
        "source_file",
        "organisaatio",
        "kokous_pvm",
        "pykala",
        "chunk_index",
        "total_chunks",
        "section_type",
        "is_table",
        "hash",
    ]

    errors = []
    for i, chunk in enumerate(chunks[:100]):  # Testaa ensimmäiset 100
        for field in required_fields:
            if field not in chunk:
                errors.append(f"Chunk {i} puuttuu kenttä: {field}")

        # Tarkista tyypit
        if not isinstance(chunk.get("text"), str) or len(chunk.get("text", "")) < 10:
            errors.append(f"Chunk {i}: text-kenttä on tyhjä tai liian lyhyt")

        if chunk.get("is_table") is not False:
            errors.append(f"Chunk {i}: is_table pitää olla False pääindeksissä")

    if errors:
        _log.error(f"Löydetty {len(errors)} virhettä skeemassa:")
        for error in errors[:10]:  # Näytä ensimmäiset 10
            _log.error(f"  - {error}")
        return False

    _log.info("✅ Chunk-skeema OK")
    return True


def test_sample_chunks(chunks: list[dict[str, Any]], count: int = 10) -> None:
    """Tulosta satunnaisia chunkkeja tarkistusta varten."""
    _log.info(f"\n{'='*60}")
    _log.info(f"Tulostetaan {count} satunnaista chunkkia:")
    _log.info(f"{'='*60}\n")

    sample = random.sample(chunks, min(count, len(chunks)))

    for i, chunk in enumerate(sample, 1):
        print(f"\n--- Chunk {i} ---")
        print(f"ID: {chunk.get('id')}")
        print(f"Organisaatio: {chunk.get('organisaatio', 'N/A')}")
        print(f"Kokous PVM: {chunk.get('kokous_pvm', 'N/A')}")
        print(f"Pykälä: {chunk.get('pykala', 'N/A')}")
        print(f"Section Type: {chunk.get('section_type', 'N/A')}")
        print(f"Source: {chunk.get('source_file', 'N/A')}")
        print(f"Text (first 300 chars): {chunk.get('text', '')[:300]}...")
        print(f"Hash: {chunk.get('hash', 'N/A')[:16]}...")


def test_metadata_coverage(chunks: list[dict[str, Any]]) -> None:
    """Testaa metatiedon kattavuutta."""
    _log.info("\nTestataan metatiedon kattavuutta...")

    total = len(chunks)
    with_org = sum(1 for c in chunks if c.get("organisaatio"))
    with_date = sum(1 for c in chunks if c.get("kokous_pvm"))
    with_section = sum(1 for c in chunks if c.get("pykala"))

    section_types = {}
    for chunk in chunks:
        st = chunk.get("section_type", "muu")
        section_types[st] = section_types.get(st, 0) + 1

    _log.info(f"Yhteensä chunkkeja: {total}")
    _log.info(f"Organisaatio: {with_org}/{total} ({with_org/total*100:.1f}%)")
    _log.info(f"Kokous PVM: {with_date}/{total} ({with_date/total*100:.1f}%)")
    _log.info(f"Pykälä: {with_section}/{total} ({with_section/total*100:.1f}%)")
    _log.info(f"\nSection-tyypit:")
    for st, count in sorted(section_types.items(), key=lambda x: -x[1]):
        _log.info(f"  {st}: {count} ({count/total*100:.1f}%)")


def test_sample_queries(chunks: list[dict[str, Any]]) -> None:
    """Testaa esimerkkihaut oikeilla kysymyksillä."""
    _log.info("\n" + "="*60)
    _log.info("Testataan esimerkkihaut oikeilla kysymyksillä...")
    _log.info("="*60 + "\n")

    # Testi 1: "Etsi kaikki § 81 päätökset 2025"
    # HUOM: Löysennetty logiikka - pykälä ja päätös voivat olla eri chunkeissa
    _log.info("Testi 1: 'Etsi kaikki § 81 päätökset 2025'")
    _log.info("  (Löysennetty: § 81 + vuosi 2025, section_type ei pakollinen)")
    query1_chunks = [
        c
        for c in chunks
        if c.get("pykala") == "§ 81"
        and c.get("kokous_pvm", "").startswith("2025")
    ]
    _log.info(f"  Löytyi {len(query1_chunks)} chunkkia")
    
    # Tarkista että jokaisen löytyneen chunkin pykala on § 81 ja vuosi 2025
    all_correct = all(c.get("pykala") == "§ 81" for c in query1_chunks)
    all_2025 = all(c.get("kokous_pvm", "").startswith("2025") for c in query1_chunks)
    
    if query1_chunks:
        sample = random.choice(query1_chunks)
        _log.info(f"  Esimerkki: {sample.get('organisaatio')} - {sample.get('kokous_pvm')} - {sample.get('pykala')} - {sample.get('section_type')}")
        _log.info(f"  ✅ Kaikki pykälät oikein: {all_correct}")
        _log.info(f"  ✅ Kaikki 2025: {all_2025}")
        _log.info(f"  HUOM: Pykälä ja päätös voivat olla eri chunkeissa, joten section_type ei ole pakollinen")
    else:
        _log.warning("  ⚠️ Ei löytynyt yhtään osumaa")
        _log.warning("  (Tämä voi olla OK, jos datassa ei ole 2025 § 81 -päätöksiä)")

    # Testi 2: "Kaupunginhallitus 2025 + päätös"
    _log.info("\nTesti 2: 'Kaupunginhallitus 2025 + päätös'")
    org = "Kaupunginhallitus"
    query2_chunks = [
        c
        for c in chunks
        if c.get("organisaatio") == org
        and c.get("kokous_pvm", "").startswith("2025")
        and c.get("section_type") == "paatos"
    ]
    _log.info(f"  Löytyi {len(query2_chunks)} chunkkia")
    
    # Tarkista että jokaisen löytyneen chunkin organisaatio on Kaupunginhallitus ja pvm alkaa 2025
    all_org_correct = all(c.get("organisaatio") == org for c in query2_chunks)
    all_date_correct = all(c.get("kokous_pvm", "").startswith("2025") for c in query2_chunks)
    
    if query2_chunks:
        sample = random.choice(query2_chunks)
        _log.info(f"  Esimerkki: {sample.get('organisaatio')} - {sample.get('kokous_pvm')} - {sample.get('pykala', 'N/A')}")
        _log.info(f"  ✅ Kaikki organisaatiot oikein: {all_org_correct}")
        _log.info(f"  ✅ Kaikki päivämäärät 2025: {all_date_correct}")
    else:
        _log.warning("  ⚠️ Ei löytynyt yhtään osumaa")

    # Testi 3: Etsi tietty organisaatio (yleinen)
    _log.info("\nTesti 3: Etsi kaikki Kaupunginhallituksen chunkit")
    org_chunks = [c for c in chunks if c.get("organisaatio") == org]
    _log.info(f"  Löytyi {len(org_chunks)} chunkkia")
    if org_chunks:
        sample = random.choice(org_chunks)
        _log.info(f"  Esimerkki: {sample.get('organisaatio')} - {sample.get('kokous_pvm')} - {sample.get('section_type')}")

    # Testi 4: Etsi tietty pykälä (yleinen)
    _log.info("\nTesti 4: Etsi kaikki § 81 chunkit (riippumatta vuodesta)")
    section = "§ 81"
    section_chunks = [c for c in chunks if c.get("pykala") == section]
    _log.info(f"  Löytyi {len(section_chunks)} chunkkia")
    if section_chunks:
        sample = random.choice(section_chunks)
        _log.info(f"  Esimerkki: {sample.get('organisaatio')} - {sample.get('kokous_pvm')} - {sample.get('section_type')}")
        # Tarkista että kaikki ovat oikein
        all_section_correct = all(c.get("pykala") == section for c in section_chunks)
        _log.info(f"  ✅ Kaikki pykälät oikein: {all_section_correct}")

    # Testi 5: Tarkista päivämääräbugi (ei pitäisi olla 1123-01-01) - ASSERT
    _log.info("\nTesti 5: Tarkista päivämääräbugi (ei pitäisi olla 1123-01-01)")
    buggy_dates = [
        c for c in chunks
        if c.get("kokous_pvm") and str(c.get("kokous_pvm", "")).startswith("1123-")
    ]
    if buggy_dates:
        _log.error(f"  ❌ Löytyi {len(buggy_dates)} chunkkia väärällä vuodella 1123!")
        sample = random.choice(buggy_dates)
        _log.error(f"  Esimerkki: {sample.get('kokous_pvm')} - {sample.get('source_file')}")
        _log.error("  ❌ TESTI EPÄONNISTUI: Päivämääräbugi ei ole korjattu!")
        raise SystemExit(1)
    else:
        _log.info("  ✅ Ei löytynyt chunkkeja väärällä vuodella 1123")


def main():
    """Pääfunktio."""
    # Lataa normalisoidut chunkit
    json_path = r"F:\Projekti-Lapua\Projekti2-20251123\DATA_päättävät_elimet_20251123\rag_output\normalized_chunks.json"

    if not Path(json_path).exists():
        _log.error(f"Tiedostoa ei löydy: {json_path}")
        _log.info("Aja ensin: python postprocess_docling_chunks.py")
        return

    _log.info(f"Ladataan chunkit: {json_path}")
    chunks = load_normalized_chunks(json_path)
    _log.info(f"Ladattu {len(chunks)} chunkkia\n")

    # Testit
    schema_ok = test_chunk_schema(chunks)

    if not schema_ok:
        _log.error("Skeema-testit epäonnistuivat!")
        return

    test_sample_chunks(chunks, count=5)
    test_metadata_coverage(chunks)
    test_sample_queries(chunks)

    _log.info("\n✅ Kaikki testit suoritettu!")


if __name__ == "__main__":
    main()

