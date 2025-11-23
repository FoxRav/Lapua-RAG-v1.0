# Käyttöesimerkit

## Perusasennus

```bash
# Kloonaa repositorio
git clone https://github.com/FoxRav/Lapua-RAG-v1.0.git
cd Lapua-RAG-v1.0

# Luo virtuaaliympäristö (suositus)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# tai
venv\Scripts\activate  # Windows

# Asenna riippuvuudet
pip install -r requirements.txt
```

## Käytä valmiita chunkkeja

### Lataa ja käytä normalisoituja chunkkeja

```python
import json
from pathlib import Path

# Lataa chunkit
chunks = []
with open("106PDF_output/normalized_chunks.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        chunk = json.loads(line)
        chunks.append(chunk)

print(f"Ladattu {len(chunks)} chunkkia")

# Esimerkki: Etsi kaikki § 81 päätökset 2025
paatokset_81_2025 = [
    c for c in chunks
    if c.get("pykala") == "§ 81"
    and c.get("kokous_pvm", "").startswith("2025")
    and c.get("section_type") == "paatos"
]

print(f"Löytyi {len(paatokset_81_2025)} § 81 päätöstä vuodelta 2025")
```

### Embedding-jobi esimerkki

```python
import json
from sentence_transformers import SentenceTransformer

# Lataa embedding-malli
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Lataa chunkit ja luo embeddingit
embeddings = []
metadata_list = []

with open("106PDF_output/normalized_chunks.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        chunk = json.loads(line)
        
        # Luo embedding
        embedding = model.encode(chunk["text"])
        embeddings.append(embedding)
        
        # Tallenna metadata
        metadata_list.append({
            "id": chunk["id"],
            "organisaatio": chunk["organisaatio"],
            "kokous_pvm": chunk["kokous_pvm"],
            "pykala": chunk["pykala"],
            "section_type": chunk["section_type"],
            "source_file": chunk["source_file"],
        })

print(f"Luotu {len(embeddings)} embeddingia")
```

## Prosessoi omat dokumentit

### 1. Prosessoi kaikki PDF-dokumentit

```bash
# Aseta root-kansio ympäristömuuttujalla
export LAPUA_RAG_ROOT_DIR="/polku/dokumentteihin"

# Tai anna komentoriviparametrina
python process_all_documents_for_rag.py /polku/dokumentteihin
```

### 2. Normalisoi chunkit

```bash
# Käytä oletuskansiota (106PDF_output) tai anna polku
python postprocess_docling_chunks.py 106PDF_output
```

### 3. Testaa

```bash
python test_sample_queries.py 106PDF_output/normalized_chunks.json
```

## Qdrant-vektori-indeksi esimerkki

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import json

# Yhdistä Qdrantiin
client = QdrantClient("localhost", port=6333)

# Luo kokoelma
client.create_collection(
    collection_name="lapua_council_v1",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)

# Lataa chunkit ja lisää indeksiin
points = []
with open("106PDF_output/normalized_chunks.jsonl", "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        chunk = json.loads(line)
        
        # Tässä pitäisi olla embedding, esimerkki:
        # vector = model.encode(chunk["text"])
        
        points.append(
            PointStruct(
                id=i,
                vector=vector,  # Täytä oikea embedding
                payload={
                    "text": chunk["text"],
                    "organisaatio": chunk["organisaatio"],
                    "kokous_pvm": chunk["kokous_pvm"],
                    "pykala": chunk["pykala"],
                    "section_type": chunk["section_type"],
                    "source_file": chunk["source_file"],
                }
            )
        )

# Lisää pisteet indeksiin
client.upsert(
    collection_name="lapua_council_v1",
    points=points
)

print(f"Lisätty {len(points)} chunkkia Qdrant-indeksiin")
```

