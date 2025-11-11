# agents/synthesizer.py
from __future__ import annotations
from typing import List, Dict, Tuple, Any
from openai import OpenAI
from tools.vecstore import rag_query
from config import MODEL_SMALL

client = OpenAI()


def synthesize_brief(topic: str, sources: int, topic_id: str | None = None) -> Dict[str, Any]:
    """
    Synthesizes a research brief using GPT and retrieved context from rag_query().
    Returns a dict -> {"brief": str, "citations": list[dict]}.
    """
    try:
        # Some versions of rag_query have topic_id first, others have it last — both handled.
        try:
            ctx = rag_query(topic_id, topic, k=15)
        except TypeError:
            ctx = rag_query(topic, k=15, topic_id=topic_id)
    except Exception as e:
        ctx = [{"chunk": f"[RAG query failed: {e}]", "meta": {}}]

    if not ctx:
        ctx = [{"chunk": "No context retrieved.", "meta": {}}]

    # Build text from retrieved chunks
    context_text = "\n\n".join(c.get("chunk", "") if isinstance(c, dict) else str(c) for c in ctx)
    if not context_text.strip():
        context_text = "No meaningful content found."

    # Prepare the GPT prompt
    system_prompt = (
        "You are a research summarizer. Write a clear, factual, concise summary "
        "of the provided context in 5–10 bullet points. Include no invented data."
    )
    user_prompt = f"Topic: {topic}\n\nContext:\n{context_text[:12000]}"

    # Query the GPT model
    try:
        response = client.chat.completions.create(
            model=MODEL_SMALL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        brief = response.choices[0].message.content.strip()
    except Exception as e:
        brief = f"[GPT generation failed: {e}]"

    # Return a consistent dict format
    return {
        "brief": brief,
        "citations": ctx
    }
