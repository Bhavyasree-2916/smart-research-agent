# agents/synthesizer.py
from __future__ import annotations
from typing import List, Tuple, Dict, Any
from openai import OpenAI
from tools.vecstore import rag_query
from config import MODEL_SMALL  # e.g., "gpt-4o-mini"

client = OpenAI()

def _normalize_ctx(ctx: Any) -> List[Dict[str, Any]]:
    """
    Ensure we always return a list of dicts with at least: {'chunk': <text>, 'meta': {...}}
    Accepts lists of strings, dicts, or any mix.
    """
    normalized: List[Dict[str, Any]] = []
    if not ctx:
        return normalized
    for item in ctx:
        if isinstance(item, dict):
            text = item.get("chunk") or item.get("text") or item.get("content") or ""
            meta = {k: v for k, v in item.items() if k not in {"chunk", "text", "content"}}
            normalized.append({"chunk": str(text), "meta": meta})
        else:
            normalized.append({"chunk": str(item), "meta": {}})
    return normalized

def synthesize_brief(topic: str, sources: int, topic_id: str | None = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Returns (brief, citations) — a tuple.
    - brief: synthesized summary as a string
    - citations: the retrieved context items (normalized list of dicts)
    """
    # rag_query should be defined as rag_query(topic_id: str, query_text: str, k: int = 8)
    # If your signature is rag_query(query_text, k=8, topic_id=None) swap the first two args.
    ctx = rag_query(topic_id or "default", topic, k=15)

    citations = _normalize_ctx(ctx)
    context_text = "\n\n".join(c["chunk"] for c in citations)[:12000]  # keep prompt reasonable

    system = (
        "You are a careful research assistant. Write a concise brief (6–10 bullet points) based ONLY on the provided context. "
        "If something is not in the context, do not invent it."
    )
    user = f"Topic: {topic}\n\nContext:\n{context_text}\n\nWrite the brief now."

    resp = client.chat.completions.create(
        model=MODEL_SMALL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    brief = resp.choices[0].message.content.strip()
    return brief, citations
