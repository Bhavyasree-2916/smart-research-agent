import os, uuid
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.utils import embedding_functions

# One persistent DB for the app
DB_DIR = os.path.join(os.getcwd(), ".chroma")
os.makedirs(DB_DIR, exist_ok=True)

_client = chromadb.PersistentClient(path=DB_DIR)
_model = SentenceTransformer("all-MiniLM-L6-v2")

def _embed(texts: List[str]) -> List[List[float]]:
    return _model.encode(texts, normalize_embeddings=True).tolist()

def get_collection(topic_id: str):
    name = f"topic_{topic_id}".replace("-", "_")
    try:
        col = _client.get_collection(name=name)
    except:
        col = _client.create_collection(name=name)
    return col

def upsert_chunks(topic_id: str, chunks: List[Dict]):
    col = get_collection(topic_id)
    texts = [c["text"] for c in chunks]
    ids   = [c["id"] for c in chunks]
    metas = [c.get("metadata", {}) for c in chunks]
    col.upsert(ids=ids, documents=texts, metadatas=metas, embeddings=_embed(texts))

def query(topic_id: str, q: str, k: int = 15) -> List[Dict]:
    col = get_collection(topic_id)
    res = col.query(query_embeddings=_embed([q]), n_results=k)
    out=[]
    for i in range(len(res["ids"][0])):
        out.append({
            "id": res["ids"][0][i],
            "text": res["documents"][0][i],
            "metadata": res["metadatas"][0][i],
        })
    return out
