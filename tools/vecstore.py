# tools/vecstore.py
# Lightweight, dependency-free vector store for Streamlit Cloud.
# Stores embeddings in-memory and uses OpenAI for embedding generation.

from __future__ import annotations

import os
import math
import uuid
from typing import List, Dict, Any, Optional, Tuple

# --- OpenAI client setup ------------------------------------------------------
# OpenAI's Python SDK looks for OPENAI_API_KEY.
# Your secrets may be stored as OPEN_API_KEY, so we mirror it if needed.
if "OPENAI_API_KEY" not in os.environ and os.getenv("OPEN_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.getenv("OPEN_API_KEY")

from openai import OpenAI  # openai==1.x
client = OpenAI()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# --- In-memory store ----------------------------------------------------------
# Each record: {id, topic_id, source, text, embedding(List[float])}
_STORE: List[Dict[str, Any]] = []


# --- Math helpers -------------------------------------------------------------
def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: List[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def _cosine(a: List[float], b: List[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return _dot(a, b) / (na * nb)


# --- Embedding ----------------------------------------------------------------
def _embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Returns one embedding list per text. Uses OpenAI embeddings API.
    """
    if not texts:
        return []
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    # openai==1.x returns .data[i].embedding
    return [d.embedding for d in resp.data]


# --- Upsert APIs --------------------------------------------------------------
def upsert_chunks_simple(chunks: List[str]) -> List[str]:
    """
    Quick insert when you don't care about topic/source tagging.
    Returns the list of ids that were added.
    """
    return upsert_chunks(topic_id="global", source="misc", chunks=chunks)


def upsert_chunks(topic_id: str, source: str, chunks: List[str]) -> List[str]:
    """
    Insert chunks with topic/source tags. Generates embeddings and stores them.
    """
    ids: List[str] = []
    if not chunks:
        return ids

    embeddings = _embed_texts(chunks)
    for text, emb in zip(chunks, embeddings):
        rid = str(uuid.uuid4())
        _STORE.append(
            {
                "id": rid,
                "topic_id": topic_id,
                "source": source,
                "text": text,
                "embedding": emb,
            }
        )
        ids.append(rid)
    return ids


# --- Query / RAG --------------------------------------------------------------
def _top_k(query_vec: List[float], pool: List[Dict[str, Any]], k: int) -> List[Tuple[float, Dict[str, Any]]]:
    scored = [(_cosine(query_vec, rec["embedding"]), rec) for rec in pool]
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[: max(0, k)]


def query(text: str, k: int = 5, topic_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return top-k matching chunks (dicts with score, text, source, id, topic_id).
    If topic_id is provided, restrict search to that topic.
    """
    if not _STORE:
        return []

    q_vec = _embed_texts([text])[0]
    pool = [r for r in _STORE if topic_id is None or r["topic_id"] == topic_id]
    if not pool:
        return []

    top = _top_k(q_vec, pool, k)
    return [
        {
            "score": round(score, 6),
            "id": rec["id"],
            "text": rec["text"],
            "source": rec["source"],
            "topic_id": rec["topic_id"],
        }
        for score, rec in top
    ]


def rag_query(topic_id: str, query_text: str, k: int = 5) -> str:
    """
    Convenience helper used by the synthesizer: returns a single
    context string concatenating the top-k chunk texts for this topic.
    """
    hits = query(query_text, k=k, topic_id=topic_id)
    if not hits:
        return ""
    # De-duplicate while keeping order
    seen = set()
    parts: List[str] = []
    for h in hits:
        t = h["text"].strip()
        if t and t not in seen:
            parts.append(t)
            seen.add(t)
    return "\n\n".join(parts)


# --- Maintenance --------------------------------------------------------------
def reset() -> None:
    """Clear the in-memory store (useful between runs/tests)."""
    _STORE.clear()


def count(topic_id: Optional[str] = None) -> int:
    """How many chunks are stored (optionally for a topic)."""
    if topic_id is None:
        return len(_STORE)
    return sum(1 for r in _STORE if r["topic_id"] == topic_id)
