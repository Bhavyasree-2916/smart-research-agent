# tools/vecstore.py
import os
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

def _embedding_fn():
    """Create safe OpenAI embedding function."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY in environment or Streamlit secrets.")
    return embedding_functions.OpenAIEmbeddingFunction(
        api_key=key,
        model_name="text-embedding-3-small"
    )

def _client():
    """Return in-memory chroma client (safe for Streamlit Cloud)."""
    return chromadb.Client(Settings(anonymized_telemetry=False))

def get_store(topic_id="default"):
    name = f"topic_{(topic_id or 'default')[:20]}"
    client = _client()
    try:
        col = client.get_or_create_collection(
            name=name,
            embedding_function=_embedding_fn()
        )
    except Exception as e:
        print(f"[Warning] Fallback: collection created without embedding. Reason: {e}")
        col = client.get_or_create_collection(name=name)
    return col

def upsert_chunks(col, texts, ids, metas=None):
    """Safely add chunks into the collection."""
    if not texts:
        return
    metas = metas or [{}] * len(texts)
    try:
        col.add(documents=texts, ids=ids, metadatas=metas)
    except Exception as e:
        print(f"[Warning] Skipped adding chunks: {e}")

def query(col, text, k=5):
    """Safe query that won’t crash on API differences."""
    if not col or not text:
        return []
    try:
        res = col.query(
            query_texts=[text],
            n_results=max(1, k),
            include=["documents", "metadatas", "ids"]
        )
        docs = (res.get("documents") or [[]])[0]
        ids = (res.get("ids") or [[]])[0]
        metas = (res.get("metadatas") or [[{}]])[0]
        output = []
        for i, doc in enumerate(docs):
            output.append({
                "id": ids[i] if i < len(ids) else f"auto-{i}",
                "text": doc,
                "metadata": metas[i] if i < len(metas) else {}
            })
        return output
    except Exception as e:
        print(f"[Warning] Query failed: {e}")
        return []
