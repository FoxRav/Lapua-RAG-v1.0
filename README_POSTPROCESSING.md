# Docling-postiprosessointi

Tämä postiprosessori normalisoi ja rikastaa Doclingin tuottamat chunkit RAG-järjestelmää varten.

## Workflow

1. **Prosessoi dokumentit**: `python process_all_documents_for_rag.py`
   - Prosessoi kaikki PDF-tiedostot
   - Luo `combined_chunks_only.json`

2. **Normalisoi chunkit**: `python postprocess_docling_chunks.py`
   - Normalisoi skeemaan
   - Suodattaa taulukot
   - Poimii metatiedot
   - Deduplikoi
   - Luo `normalized_chunks.json` ja `normalized_chunks.jsonl`

3. **Testaa**: `python test_sample_queries.py`
   - Tarkistaa skeeman
   - Näyttää esimerkkejä
   - Testaa hakuja

## Final Chunk Schema

```json
{
  "id": "doc_0_chunk_12",
  "text": "...",                    // contextualized_text (embeddingiin)
  "source_file": "Lapua/2025/...",
  "organisaatio": "Kaupunginhallitus",
  "kokous_pvm": "2025-11-10",
  "pykälä": "§ 81",
  "chunk_index": 12,
  "total_chunks": 45,
  "section_type": "paatos | perustelut | muutoksenhaku | talous | muu",
  "is_table": false,
  "hash": "sha1-hash"
}
```

## Chunkkien koko-optimointi (Lapua-RAG)

### Optimaaliset asetukset
- **Target**: ~384 tokenia per chunk
- **Max**: 512 tokenia (ehdoton yläraja)
- **Min**: 150 tokenia (poikkeukset: lyhyet päätökset)
- **Rakenne**: HybridChunker erottelee rakenteen mukaan (päätökset, pykälät)

### Miksi 384-512 tokenia?
- RAG-haku: 6-8 chunkkia × 384 ≈ 2300 tokenia → sopii 8k-16k context-malleille
- Yksi chunk = yksi ajatuskokonaisuus (päätös + perustelu)
- Ei liikaa "mössöä" yhteen chunkkiin
- Riittävästi kontekstia päätösten ymmärtämiseen

## Ominaisuudet

### 1. Taulukoiden suodatus
- Taulukot jätetään pois pääindeksistä
- Säilytetään erillisessä listassa jos tarvitaan myöhemmin

### 2. Metatietojen poiminta
- **Organisaatio**: Etsitään tiedostopolusta tai tekstistä
- **Kokous PVM**: Parsitaan päivämäärä YYYY-MM-DD -muotoon
- **Pykälä**: Etsitään §-merkkejä ja pykälänumeroita

### 3. Section-tyypit
- **paatos**: Päätökset
- **perustelut**: Perustelut
- **muutoksenhaku**: Muutoksenhakuohjeet
- **talous**: Talousarvio, budjetti
- **muu**: Muu sisältö

### 4. Chunkkien koon filtteröinti
- Filtteröi liian lyhyet chunkit (<150 tokenia)
- Poikkeus: lyhyet päätökset säilytetään
- Varoittaa jos chunk ylittää max_tokens-rajan

### 5. Deduplikaatio
- SHA1-hash normalisoidusta tekstistä
- Identtiset chunkit jätetään pois
- Poistaa toistuvat muutoksenhakuohjeet

## Käyttö

### Postiprosessointi

```bash
python postprocess_docling_chunks.py
```

### Testit

```bash
python test_sample_queries.py
```

## Output

- **normalized_chunks.json**: Täysi dataset metadatalla
- **normalized_chunks.jsonl**: Yksi chunk per rivi (sopii suoraan vektori-indeksointiin)

## RAG-integraatio

Käytä normalisoituja chunkkeja RAG-järjestelmässä:

```python
import json

# Lataa normalisoidut chunkit
with open("normalized_chunks.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Käytä chunkkeja
for chunk in data["chunks"]:
    text = chunk["text"]  # Embeddingiin
    metadata = {
        "organisaatio": chunk["organisaatio"],
        "kokous_pvm": chunk["kokous_pvm"],
        "pykala": chunk["pykala"],
        "section_type": chunk["section_type"],
    }
    
    # Filtteröinti metadatan perusteella
    if chunk["organisaatio"] == "Kaupunginhallitus":
        # Prosessoi vain kaupunginhallituksen chunkit
        pass
```

## Tarkistuslista

- ✅ Final-chunk-skeema määritelty
- ✅ Taulukot suodatettu pois
- ✅ Metatiedot poimittu (organisaatio, pvm, pykälä)
- ✅ Deduplikaatio toteutettu
- ✅ Sanity testit lisätty

