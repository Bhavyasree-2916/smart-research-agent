# tools/vecstore.py
# Minimal vector store with optional Chroma and robust OpenAI embeddings.
# - If chromadb is installed: uses a persistent DB (./.chroma)
# - Otherwise: falls back to a simple in-memory store per topic_id
# - Uses OpenAI >= 1.3x style client and text-embedding-3-small by default

from __future__ import annotations

import os
import time
import math
import uuid
from typing import List, Dict, Any, Optional

# ---------- OpenAI client (new SDK) ----------
from openai import OpenAI
client = OpenAI()  # reads OPENAI_API_KEY from env/Streamlit secrets

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

def _embed_once(text: str) -> List[float]:
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text, timeout=30)
    return resp.data[0].embedding

def embed(text: str, retries: int = 3, backoff: float = 2.0) -> List[float]:
    last_err = None
    for i in range(retries):
        try:
            return _embed_once(text)
        except Exception as e:
            last_err = e
            time.sleep(backoff * (i + 1))
    raise last_err


# ---------- Optional Chroma backend ----------
_CHROMA_OK = True
try:
    import chromadb  # type: ignore
    from chromadb.utils import embedding_functions  # noqa: F401 (kept for compatibility)
except Exception:
    _CHROMA_OK = False


# ---------- Simple in-memory fallback ----------
# Structure: _MEM[topic_id] = {"ids": [], "embs": [[...]], "texts": [], "metas": []}
_MEM: Dict[str, Dict[str, List[Any]]] = {}

def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    s = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(y*y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return s / (na * nb)


# ---------- Public API ----------
def get_store(topic_id: str):
    """
    Returns a collection-like object with:
      - upsert(texts, metadatas, ids)
      - query(query_texts=[...], n_results=k) -> dict
    """
    if _CHROMA_OK:
        client_chroma = chromadb.PersistentClient(path=os.path.abspath("./.chroma"))
        return _ChromaCollection(client_chroma, topic_id)
    else:
        # ensure mem bucket
        _MEM.setdefault(topic_id, {"ids": [], "embs": [], "texts": [], "metas": []})
        return _MemCollection(topic_id)


def upsert_chunks(topic_id: str, texts: List[str], metadatas: List[Dict[str, Any]]) -> None:
    """
    Embeds + writes chunks into the vector store for this topic_id.
    """
    if not texts:
        return

    # make ids stable if provided inside metadata; otherwise random
    ids = []
    for m in metadatas:
        ids.append(m.get("id") or str(uuid.uuid4()))

    vs = get_store(topic_id)

    # embed in a simple loop (Streamlit Cloud prefers small batches)
    embs = [embed(t) for t in texts]
    vs.upsert(texts=texts, metadatas=metadatas, ids=ids, embeddings=embs)


def rag_query(topic_id: str, query: str, k: int = 8) -> List[Dict[str, Any]]:
    """
    Returns top-k context items as a list of {text, metadata}
    """
    vs = get_store(topic_id)
    res = vs.query(query_texts=[query], n_results=k)
    out = []
    # normalize to list-of-dicts
    for i in range(len(res["documents"][0])):
        out.append({
            "text": res["documents"][0][i],
            "metadata": res["metadatas"][0][i]
        })
    return out


# ---------- Backends ----------
class _ChromaCollection:
    def __init__(self, client_chroma, topic_id: str):
        self._col = client_chroma.get_or_create_collection(name=f"topic_{topic_id}")

    def upsert(self, texts, metadatas, ids, embeddings):
        self._col.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings
        )

    def query(self, query_texts: List[str], n_results: int = 8) -> Dict[str, Any]:
        # embed the query ourselves for consistency/retry control
        q_emb = [embed(query_texts[0])]
        res = self._col.query(query_embeddings=q_emb, n_results=n_results)
        # Chroma returns keys: ids, distances, documents, metadatas
        return {
            "ids": res.get("ids", [[]]),
            "documents": res.get("documents", [[]]),
            "metadatas": res.get("metadatas", [[]]),
            "distances": res.get("distances", [[]]),
        }


class _MemCollection:
    def __init__(self, topic_id: str):
        self._bucket = _MEM[topic_id]

    def upsert(self, texts, metadatas, ids, embeddings):
        self._bucket["ids"].extend(ids)
        self._bucket["texts"].extend(texts)
        self._bucket["metas"].extend(metadatas)
        self._bucket["embs"].extend(embeddings)

    def query(self, query_texts: List[str], n_results: int = 8) -> Dict[str, Any]:
        q = embed(query_texts[0])
        sims = [(_cosine(q, e), i) for i, e in enumerate(self._bucket["embs"])]
        sims.sort(reverse=True)
        take = sims[:n_results]

        docs = []
        metas = []
        ids = []
        dists = []
        for score, idx in take:
            docs.append(self._bucket["texts"][idx])
            metas.append(self._bucket["metas"][idx])
            ids.append(self._bucket["ids"][idx])
            # convert similarity to pseudo-distance
            dists.append(1.0 - score)

        return {
            "ids": [ids],
            "documents": [docs],
            "metadatas": [metas],
            "distances": [dists],
        }
