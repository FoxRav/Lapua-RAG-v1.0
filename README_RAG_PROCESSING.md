# PDF-prosessointi RAG-järjestelmää varten

Tämä skripti prosessoi PDF-dokumentteja optimaalisesti RAG (Retrieval-Augmented Generation) -järjestelmiä varten.

## Asennus

```bash
# Perusasennus
pip install docling

# Jos käytät embedding-mallia (suositus RAG:ia varten)
pip install docling transformers
```

## Käyttö

### Yksinkertainen käyttö

```python
from process_pdf_for_rag import process_pdf_for_rag

result = process_pdf_for_rag(
    pdf_path="polku/tiedostoon.pdf"
)
```

### Käyttö oman embedding-mallin kanssa

```python
from process_pdf_for_rag import process_pdf_for_rag

result = process_pdf_for_rag(
    pdf_path="polku/tiedostoon.pdf",
    embed_model_id="sentence-transformers/all-MiniLM-L6-v2"
)
```

## Output

Skripti luo seuraavat tiedostot `rag_output/`-kansioon:

1. **`{tiedosto}_rag.json`** - Chunkit JSON-muodossa RAG:ia varten
   - Sisältää: chunkit, metadata, kontekstualisoidut tekstit
   
2. **`{tiedosto}_full.md`** - Koko dokumentti Markdown-muodossa

3. **`{tiedosto}_chunks.md`** - Chunkit ihmisluettavassa muodossa

4. **`{tiedosto}_docling.json`** - Täysi DoclingDocument JSON-rakenne

## RAG-integraatio

### JSON-tiedoston käyttö

```python
import json

with open("rag_output/tiedosto_rag.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Käytä chunkkeja RAG:issa
for chunk in data["chunks"]:
    text = chunk["contextualized_text"]  # Käytä tätä embedding:ia varten
    metadata = chunk["metadata"]  # Käytä tätä filtteröintiin
```

### Chunk-metadata

Jokainen chunk sisältää:
- `text`: Alkuperäinen teksti
- `contextualized_text`: Kontekstualisoitu teksti (suositus embedding:ia varten)
- `metadata`: Lähdetiedot, sivu, jne.

## Skaalautuvuus

Skripti on suunniteltu käsittelemään satoja dokumentteja. Käytä batch-prosessointia:

```python
from pathlib import Path
from process_pdf_for_rag import process_pdf_for_rag

pdf_dir = Path("pdf_kansio")
for pdf_file in pdf_dir.glob("*.pdf"):
    try:
        process_pdf_for_rag(pdf_file)
    except Exception as e:
        print(f"Virhe prosessoinnissa {pdf_file}: {e}")
```

## Optimaaliset asetukset

Skripti käyttää automaattisesti:
- ✅ OCR skannatuille PDF:ille
- ✅ Layout detection (sivun rakenne)
- ✅ Table structure extraction (taulukoiden rakenne)
- ✅ HybridChunker (säilyttää kontekstin)
- ✅ Parhaan backendin (DoclingParseV4DocumentBackend)

## Tietoja

- **OCR**: Automaattisesti tunnistaa tarvitseeko PDF OCR:ia
- **Chunking**: HybridChunker säilyttää dokumentin rakenteen ja kontekstin
- **Metadata**: Jokainen chunk sisältää lähdetiedot ja sivunumeron


