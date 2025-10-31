# agents/synthesizer.py
from typing import List, Dict
import textwrap
from config import OPENAI_API_KEY, MODEL_MAIN
from tools.vecstore import query as rag_query  # ✅ only this import

def _llm_summarize(context_blobs: List[Dict], topic: str) -> str:
    if not OPENAI_API_KEY:
        joined = " ".join([c["text"][:300] for c in context_blobs])[:2000]
        return textwrap.shorten(f"{topic}: {joined}", width=900, placeholder="...")
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    cites = "\n".join([f"[{i+1}] {c['metadata'].get('url','')}" for i,c in enumerate(context_blobs)])
    prompt = f"""Write a 250–350 word brief about: {topic}.
Use simple language (grade <= 10).
Cite with [1], [2], ... mapping to these sources:
{cites}
Base your answer ONLY on the provided context.
"""
    msg = client.chat.completions.create(
        model=MODEL_MAIN,
        messages=[{"role":"user","content":prompt}],
        temperature=0.3,
    )
    return msg.choices[0].message.content.strip()

def synthesize_brief(topic: str, sources: List[Dict], topic_id: str = "default"):
    ctx = rag_query(topic_id, topic, k=15)
    if not ctx:  # fallback if nothing in vector store yet
        top = sources[:3] if len(sources) > 3 else sources
        ctx = [{"text": s["text"], "metadata": {"url": s["url"], "domain": s["domain"]}} for s in top]

    brief = _llm_summarize(ctx, topic)

    # build citations from retrieved context
    seen, citations = set(), []
    for c in ctx:
        url = c["metadata"].get("url", "")
        dom = c["metadata"].get("domain", "")
        if url and url not in seen:
            citations.append({"id": len(citations)+1, "url": url, "domain": dom})
            seen.add(url)
        if len(citations) >= 5:
            break

    return {"brief": brief, "citations": citations}
