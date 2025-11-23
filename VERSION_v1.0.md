# Lapua-RAG Pipeline v1.0 - Final Dataset

## Yleiskuvaus

Tämä on **v1.0 "Lapua-päättävät_elimet"** -versio Docling-pohjaisesta RAG-pipelinesta, joka prosessoi 106 pöytäkirjaa Lapuan kaupungin päättävistä elimistä.

## Dataset

- **Input**: 106 PDF-pöytäkirjaa
- **Output**: `normalized_chunks.jsonl` (6138 chunkkia)
- **Taulukot**: `tables_normalized.jsonl` (556 taulukkoa, erillinen indeksi)

## Chunk-tilastot

- **Alkuperäisiä chunkkeja**: 11 351
- **Normalisoituja chunkkeja**: 6 138
- **Taulukoita tallennettu**: 556
- **Duplikaatteja suodatettu**: 3 739
- **Keskimääräinen chunk-koko**: ~145 tokenia
- **Tavoite-alueella** (268-512 tokenia): 17.8% (1095/6138)

## Metatiedon kattavuus

- **Organisaatio**: 99.9% (6133/6138)
- **Kokous PVM**: 99.9% (6133/6138)
- **Pykälä**: 34.2% (2098/6138) - odotettavissa, koska kaikissa chunkeissa ei ole pykälänumeroa

## Chunk-skeema

```json
{
  "id": "doc_0_chunk_33",
  "text": "...",  // contextualized_text menee embeddingiin
  "source_file": "Ympäristölautakunta\\2025\\...",
  "organisaatio": "Kaupunginhallitus",
  "kokous_pvm": "2025-06-10",
  "pykala": "§ 33",
  "chunk_index": 33,
  "total_chunks": 45,
  "section_type": "paatos | perustelut | muutoksenhaku | talous | muu",
  "is_table": false,
  "hash": "..."
}
```

## Pipeline-vaiheet

1. **Docling-prosessointi**: `process_all_documents_for_rag.py`
   - Prosessoi 106 PDF-dokumenttia
   - Käyttää HybridChunker (max_tokens=512)
   - Output: `combined_chunks_only.json`

2. **Postprosessointi**: `postprocess_docling_chunks.py`
   - Normalisoi chunkit lopulliseen skeemaan
   - Suodattaa taulukot erilliseen tiedostoon
   - Deduplikoi toistuvat muutoksenhakuohjeet
   - Yhdistää mikrochunkit (<30 tokenia)
   - Korjaa päivämääräbugit (1123 → oikea päivämäärä)
   - Output: `normalized_chunks.jsonl` + `tables_normalized.jsonl`

3. **Testaus**: `test_sample_queries.py`
   - Tarkistaa chunk-skeeman
   - Testaa metatiedon kattavuuden
   - Validoi päivämääräbugin korjauksen
   - Testaa esimerkkihaut (§ 81, Kaupunginhallitus 2025, jne.)

## Päivämäärälogiikka

- **Ensisijaisesti**: Tiedostonimi (esim. `Pöytäkirja-Kaupunginvaltuusto - 02.06.2025`)
- **Backup**: Tekstistä löytyvä päivämäärä (tarkistaa että vuosi on 2000-2035)
- **Jos ei löydy**: `None` (ei 1123-01-01 -placeholderia)

## Käyttö embeddingeissä

Käytä **`normalized_chunks.jsonl`** -tiedostoa embedding-jobissa:

- **Embeddattava teksti**: `text`-kenttä (sisältää jo kontekstin)
- **Metadata** (vähintään):
  - `organisaatio`
  - `kokous_pvm`
  - `pykala`
  - `section_type`
  - `source_file`
  - `id`

## Testit

Aja aina kun muutat:
- Date parseria
- Chunkkauslogiikkaa
- Metadataparseria

```bash
python test_sample_queries.py
```

**Kriittiset testit**:
- § 81 + 2025 → odotettu: 7 osumaa
- Kaupunginhallitus 2025 + päätös → odotettu: 393 osumaa
- **0 kpl vuotta 1123** → jos tämä ilmestyy takaisin, testi epäonnistuu

## Seuraavat askeleet

1. ✅ Datasetti lukittu v1.0:ksi
2. ✅ Git-versioitu
3. ⏭️ Embedding-jobi (`normalized_chunks.jsonl`)
4. ⏭️ End-to-end LLM-testi (Qdrant + chat-käyttöliittymä)

## Versiohistoria

- **v1.0** (2025-11-23): Final dataset, päivämääräbugi korjattu, testit validoitu

