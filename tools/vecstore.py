# tools/vecstore.py
import os
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# ---- Configure an OpenAI embedding function (no torch needed) ----
def _embedding_fn():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is required on Streamlit Cloud to build embeddings. "
            "Set it in Settings → Secrets."
        )
    return embedding_functions.OpenAIEmbeddingFunction(
        api_key=key,
        model_name="text-embedding-3-small"
    )

def _client():
    # in-memory DB is fine for the mini project
    return chromadb.Client(Settings(anonymized_telemetry=False))

def get_store(topic_id: str = "default"):
    coll_name = f"topic_{topic_id[:8]}"
    client = _client()
    col = client.get_or_create_collection(
        name=coll_name,
        embedding_function=_embedding_fn()
    )
    return col

# ---- Helpers used by researcher/synthesizer ----
def upsert_chunks(col, texts, ids, metas=None):
    metas = metas or [{}] * len(texts)
    col.add(documents=texts, ids=ids, metadatas=metas)

def query(col, text, k=5):
    res = col.query(query_texts=[text], n_results=k)
    out = []
    for i in range(len(res.get("ids", [[]])[0])):
        out.append({
            "id": res["ids"][0][i],
            "text": res["documents"][0][i],
            "metadata": (res.get("metadatas") or [[{}]])[0][i]
        })
    return out
