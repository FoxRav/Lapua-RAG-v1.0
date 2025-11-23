# Seuraavat askeleet - Embedding & RAG

## 1. Embedding-jobi

### Input
- **Tiedosto**: `normalized_chunks.jsonl` (6138 chunkkia)
- **Sijainti**: Määritä oma polku ympäristömuuttujalla tai komentoriviparametrilla

### Embeddattava teksti
- **Kenttä**: `text` (sisältää jo kontekstin, esim. "Ympäristölautakunta, 24.10.2023, § 67 ...")
- **Ei tarvitse**: lisätä kontekstia, se on jo normalisoitu

### Metadata (tallenna vähintään)
```python
metadata = {
    "organisaatio": chunk["organisaatio"],
    "kokous_pvm": chunk["kokous_pvm"],
    "pykala": chunk["pykala"],
    "section_type": chunk["section_type"],
    "source_file": chunk["source_file"],
    "id": chunk["id"],
    "chunk_index": chunk.get("chunk_index"),
}
```

### Käyttö
- **Perus-semantiikkahaku**: käytä `text`-kenttää embeddingiin
- **Filtterit**: käytä metadataa (esim. "vain kaupunginhallitus 2025", "vain pykälä § 81")

## 2. Vector-index (Qdrant/ChromaDB)

### Suositus: Qdrant
- Hyvä metadata-filtterointi
- Skalautuu hyvin
- Vapaa käyttö (self-hosted)

### Indeksointi
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# Luo kokoelma
client.create_collection(
    collection_name="lapua_council_v1",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),  # tai embedding-mallin koko
)
```

## 3. End-to-end LLM-testi

### Testikysymykset

1. **"Mitä päätettiin Lapuan Virkiä superpesisjoukkueen yhteistyöstä vuodelle 2026?"**
   - Odotettu: § 398, Kaupunginhallitus, 2025-11-18
   - Tarkista: vastaus käyttää oikeaa organisaatiota + päivämäärää + pykälää

2. **"Miten § 81 päätöksissä 2025 perustellaan takausvastuu?"**
   - Odotettu: löytyy 7 chunkkia (§ 81 + 2025)
   - Tarkista: kaikki chunkit ovat oikea pykälä ja vuosi

3. **"Mitä päätettiin sivistyslautakunnassa 27.01.2025 esiopetuksen ostopalveluista?"**
   - Odotettu: Sivistyslautakunta, 2025-01-27
   - Tarkista: vastaus viittaa oikeaan päivämäärään ja organisaatioon

### Validoi
- ✅ Vastaus käyttää oikeita chunkkeja (organisaatio + päivämäärä + pykälä)
- ✅ Vastaus pystyy antamaan lyhyen tiivistelmän
- ✅ Vastaus viittaa pykälään

## 4. CI/Testaus

### Aja aina kun muutat
```bash
python test_sample_queries.py
```

### Kriittiset testit
- § 81 + 2025 → 7 osumaa
- Kaupunginhallitus 2025 + päätös → 393 osumaa
- **0 kpl vuotta 1123** (assertion - jos tämä epäonnistuu, tiedät heti)

## 5. Mahdolliset jatkokehitykset

- **GraphRAG**: Rakenna graafi organisaatioista, päivämääristä, pykälistä
- **NodeRAG**: Hierarkkinen rakenne (organisaatio → päivämäärä → pykälä)
- **Talous/BI-kerros**: Käytä `tables_normalized.jsonl` -tiedostoa SQL/OLAP-analyyseihin

**HUOM**: Kaikki nämä voivat käyttää *samaa* perusdatasettiä (`normalized_chunks.jsonl`) ilman, että sinun tarvitsee koskea PDF-tasoon.

