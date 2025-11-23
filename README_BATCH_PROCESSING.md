# Batch-prosessointi kaikille dokumenteille RAG:ia varten

Tämä skripti prosessoi kaikki PDF-dokumentit rekursiivisesti annetusta kansiosta ja yhdistää ne yhteen suureen RAG-datasetiin.

## Käyttö

### Yksinkertainen käyttö

```bash
python process_all_documents_for_rag.py
```

### PowerShell-skriptin käyttö (suositus Windowsissa)

```powershell
.\run_rag_processing.ps1
```

Tai määritä skripti:
```powershell
.\run_rag_processing.ps1 -Script "process_all_documents_for_rag.py"
```

## Output

Skripti luo seuraavat tiedostot `rag_output/`-kansioon:

### Yhdistetyt tiedostot (kaikki dokumentit yhdessä)

1. **`combined_rag_dataset.json`** - Täysi dataset kaikilla dokumenteilla ja chunkkeilla
   - `metadata`: Yhteenveto prosessoinnista
   - `documents`: Lista kaikista dokumenteista
   - `all_chunks`: Kaikki chunkit yhdessä listassa

2. **`combined_chunks_only.json`** - Yksinkertaistettu versio (vain chunkit)
   - Sopii suoraan RAG-järjestelmään
   - Sisältää metadataa lähdedokumenteista

### Yksittäiset dokumentit (valinnainen)

Jos `save_individual=True`:
- `individual_documents/{dokumentti}/` - Jokaiselle dokumentille oma kansio
  - `*_rag.json` - Dokumentin chunkit
  - `*_full.md` - Dokumentti Markdown-muodossa

## RAG-integraatio

### Käytä yhdistettyä datasetia

```python
import json

# Lataa yhdistetty dataset
with open("rag_output/combined_chunks_only.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Käytä chunkkeja RAG:issa
for chunk in data["chunks"]:
    text = chunk["contextualized_text"]  # Käytä tätä embedding:ia varten
    metadata = chunk["metadata"]  # Sisältää lähdetiedot
    
    # Metadata sisältää:
    # - source_file: Täysi polku tiedostoon
    # - source_name: Tiedoston nimi
    # - source_relative_path: Suhteellinen polku
    # - chunk_index: Chunkin indeksi dokumentissa
    # - global_chunk_id: Globaali indeksi kaikista chunkkeista
    # - document_index: Dokumentin indeksi listassa
```

## Chunk-metadata

Jokainen chunk sisältää:
- `text`: Alkuperäinen teksti
- `contextualized_text`: Kontekstualisoitu teksti (suositus embedding:ia varten)
- `metadata`: Lähdetiedot, sivu, globaali ID, jne.
- `global_chunk_id`: Yksilöllinen ID kaikista chunkkeista
- `document_index`: Indeksi dokumentissa

## Edistymisen seuranta

Skripti näyttää:
- Reaaliaikaisen edistymisen
- Arvioidun jäljellä olevan ajan
- Yhteenvedon prosessoinnin jälkeen

## Virheenkäsittely

Skripti jatkaa prosessointia vaikka jokin dokumentti epäonnistuisi:
- Epäonnistuneet dokumentit kirjataan lokiin
- Muut dokumentit prosessoidaan normaalisti
- Yhteenvedossa näkyy onnistuneiden ja epäonnistuneiden määrä

## Suorituskyky

- Prosessoi dokumentit peräkkäin (varmistaa stabiiliuden)
- Käyttää GPU:ta jos saatavilla (CUDA)
- Automaattinen OCR-valinta
- Optimoidut batch-koot

## Esimerkki outputista

```json
{
  "metadata": {
    "total_documents": 106,
    "processed_documents": 105,
    "failed_documents": 1,
    "total_chunks": 15234,
    "processing_date": "2025-11-23 15:45:00",
    "root_directory": "<root_kansio>"
  },
  "chunks": [
    {
      "global_chunk_id": 0,
      "text": "...",
      "contextualized_text": "...",
      "metadata": {
        "source_file": "...",
        "source_name": "dokumentti1.pdf",
        "chunk_index": 0,
        "document_index": 0
      }
    }
  ]
}
```

