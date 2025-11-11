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

def synthesize_brief(topic: str, sources: int, topic_id: str = None):
    ctx = rag_query(topic_id, topic, k=15)
    brief = make_brief(topic, ctx)  # whatever you call your summarizer
    citations = ctx                  # or extract only what you need
    return brief, citations
