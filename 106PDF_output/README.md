# 106PDF_output - Lapua-RAG v1.0 Dataset

**HUOM**: Tämä kansio on siirretty projektin juureen (`106PDF_output/`).

Tämä kansio sisältää v1.0 -version normalisoidut chunkit 106 pöytäkirjasta.

## Tiedostot

### `normalized_chunks.jsonl` (5.73 MB)
- **6138 normalisoitua chunkkia**
- Valmis embedding-jobille
- Sisältää metadatat: organisaatio, kokous_pvm, pykälä, section_type

### `tables_normalized.jsonl` (0.51 MB)
- **556 taulukkoa** erillisessä indeksissä
- Ei sisällytetty pääindeksiin (vektori-RAG)

## Käyttö

### Embedding-jobissa
```python
import json

with open("106PDF_output/normalized_chunks.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        chunk = json.loads(line)
        # chunk["text"] → embedding
        # chunk["organisaatio"], chunk["kokous_pvm"], jne. → metadata
```

### Testaaminen
```bash
python test_sample_queries.py 106PDF_output/normalized_chunks.json
```

## Muut tiedostot

Seuraavat tiedostot eivät ole GitHubissa (liian suuria):
- `combined_chunks_only.json` (19.64 MB)
- `combined_rag_dataset.json` (40.52 MB)
- `normalized_chunks.json` (6.25 MB)
- `individual_documents/` (106 JSON + 106 MD)

Nämä voidaan generoida uudelleen ajamalla:
```bash
python process_all_documents_for_rag.py <root_kansio>
python postprocess_docling_chunks.py 106PDF_output
```

