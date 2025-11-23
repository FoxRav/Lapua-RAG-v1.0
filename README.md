# Lapua-RAG: Docling-pohjainen RAG-pipeline

RAG-pipeline Lapuan kaupungin päättävien elinten pöytäkirjoille käyttäen Docling-dokumenttiprosessointia.

## Versio

**v1.0** - Final dataset (2025-11-23)

Katso `VERSION_v1.0.md` yksityiskohdista.

## Projektin rakenne

```
.
├── process_all_documents_for_rag.py    # Docling-batch-prosessointi (106 PDF)
├── postprocess_docling_chunks.py        # Normalisointi & rikastus
├── test_sample_queries.py               # Validaatiotestit
├── run_rag_processing.ps1              # PowerShell-wrapper (Windows)
├── fix_hf_cache.ps1                     # HuggingFace cache -korjaus
└── README_*.md                          # Dokumentaatio
```

## Nopea alku

### 1. Prosessoi dokumentit

```bash
# Windows PowerShell
.\run_rag_processing.ps1

# Tai suoraan Python
python process_all_documents_for_rag.py
```

### 2. Normalisoi chunkit

```bash
python postprocess_docling_chunks.py
```

Output (tallennetaan `106PDF_output/`):
- `normalized_chunks.jsonl` (6138 chunkkia) - **käytä tätä embeddingeissä**
- `tables_normalized.jsonl` (556 taulukkoa) - erillinen indeksi

### 3. Testaa

```bash
python test_sample_queries.py
```

## Dataset

- **Input**: 106 PDF-pöytäkirjaa
- **Output**: `normalized_chunks.jsonl` (6138 chunkkia)
- **Metatiedon kattavuus**: 99.9% organisaatio, 99.9% päivämäärä, 34.2% pykälä

**HUOM**: Valmiit normalisoidut chunkit ovat saatavilla `106PDF_output/` -kansiossa. Vektori-indeksi tulee **v2.0** -versiossa.

## Chunk-skeema

```json
{
  "id": "doc_0_chunk_33",
  "text": "...",  // contextualized_text → embedding
  "source_file": "Ympäristölautakunta\\2025\\...",
  "organisaatio": "Kaupunginhallitus",
  "kokous_pvm": "2025-06-10",
  "pykala": "§ 33",
  "section_type": "paatos",
  "hash": "..."
}
```

## Seuraavat askeleet

1. ✅ **v1.0 dataset lukittu** - `normalized_chunks.jsonl`
2. ⏭️ **Embedding-jobi** - käytä `normalized_chunks.jsonl`:ää
3. ⏭️ **Vector-index** (Qdrant/ChromaDB)
4. ⏭️ **End-to-end LLM-testi** - chat-käyttöliittymä

**HUOM**: v1.0 sisältää vain normalisoidun datasetin. Vektori-indeksi tulee **v2.0** -versiossa.

## Testaus

Aja `test_sample_queries.py` aina kun muutat:
- Date parseria
- Chunkkauslogiikkaa
- Metadataparseria

**Kriittiset testit**:
- § 81 + 2025 → 7 osumaa
- Kaupunginhallitus 2025 + päätös → 393 osumaa
- **0 kpl vuotta 1123** (assertion)

## Dokumentaatio

- `VERSION_v1.0.md` - Versiohistoria ja yksityiskohdat
- `README_BATCH_PROCESSING.md` - Batch-prosessoinnin dokumentaatio
- `README_POSTPROCESSING.md` - Postprosessoinnin dokumentaatio
- `CHUNK_OPTIMIZATION.md` - Chunk-optimointistrategia

## Git

```bash
git log --oneline
# f5ca7bb feat: finalize Lapua council docling pipeline (v1.0)
```

## Lisenssi

Projekti käyttää Docling-kirjastoa (MIT-lisenssi).
