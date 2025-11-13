# app/app.py
from __future__ import annotations

import os
import uuid
import streamlit as st

# --- Optional cloud helpers (Supabase). If not present, we no-op gracefully.
try:
    from tools.cloud import save_run, is_configured, load_brief  # type: ignore
except Exception:
    def is_configured() -> bool:
        return False
    def save_run(*args, **kwargs):
        return None
    def load_brief(*args, **kwargs):
        return None

# --- Local modules
from agents.researcher import research_from_web           # must return list[str] or list[dict]
from agents.synthesizer import synthesize_brief           # returns (brief, citations) OR dict
from tools.vecstore import upsert_chunks_simple, rag_query
from config import MODEL_SMALL

# --- Optional readability checks
try:
    from tools.validation import flesch_kincaid_grade
except Exception:
    def flesch_kincaid_grade(text: str) -> float:
        return 0.0

# ----------------- UI -----------------
st.set_page_config(page_title="Smart Research → Brief + Citations", page_icon="🧠", layout="wide")
st.title("🧠 Smart Research → Brief + Citations")

with st.sidebar:
    st.header("About")
    st.write(
        "Enter a topic. The agent plans queries, fetches sources (e.g., Wikipedia), "
        "builds a small vector index, synthesizes a brief using GPT, and shows citations."
    )
    if is_configured():
        st.success("Cloud save: ON (Supabase)")
    else:
        st.info("Cloud save: OFF (no Supabase secrets found)")

# Inputs
topic = st.text_input("Topic", placeholder="e.g., LLM agents in healthcare")
sources_per_subquery = st.slider("Sources per subquery", min_value=1, max_value=10, value=3)
run = st.button("Run Agent", type="primary")

# Session state
if "topic_id" not in st.session_state:
    st.session_state.topic_id = None

# ----------------- Helpers -----------------
def _normalize_chunks(chunks) -> list[dict]:
    """Ensure chunks become a list of dicts with at least {'chunk': <text>}."""
    norm = []
    if not chunks:
        return norm
    for c in chunks:
        if isinstance(c, dict):
            text = c.get("chunk") or c.get("text") or c.get("content") or ""
            meta = {k: v for k, v in c.items() if k not in {"chunk", "text", "content"}}
            norm.append({"chunk": str(text), "meta": meta})
        else:
            norm.append({"chunk": str(c), "meta": {}})
    return norm

def _unpack_brief(result):
    """Accept (brief, citations) OR {'brief':..., 'citations':...}."""
    if isinstance(result, tuple) and len(result) == 2:
        brief, citations = result
    elif isinstance(result, dict):
        brief = result.get("brief") or result.get("summary") or ""
        citations = result.get("citations") or result.get("sources") or []
    else:
        raise ValueError("Unexpected return from synthesize_brief()")
    return brief, citations

# ----------------- Main -----------------
if run:
    if not topic.strip():
        st.warning("Please enter a topic.")
        st.stop()

    topic_id = st.session_state.topic_id or str(uuid.uuid4())
    st.session_state.topic_id = topic_id

    with st.expander("1) Researching & collecting sources...", expanded=True):
        with st.spinner("Searching and collecting context…"):
            raw_chunks = research_from_web(topic, sources_per_subquery)
            chunks = _normalize_chunks(raw_chunks)
            st.write(f"Collected **{len(chunks)}** chunks.")
            if chunks:
                upsert_chunks_simple(topic_id, chunks)
                st.success("Indexed in vector store.")

    with st.expander("2) Synthesizing brief...", expanded=True):
        with st.spinner("Summarizing from retrieved context…"):
            result = synthesize_brief(topic, sources_per_subquery, topic_id=topic_id)
            brief, citations = _unpack_brief(result)

            # Optional cloud save
            try:
                if is_configured():
                    save_run(topic_id=topic_id, topic=topic, brief=brief, citations=citations)
            except Exception:
                pass

            st.subheader("Brief")
            st.markdown(brief)

            grade = flesch_kincaid_grade(brief)
            st.caption(f"Readability (Flesch–Kincaid grade): {grade:.1f}")

    with st.expander("3) Citations (retrieved context)", expanded=False):
        if not citations:
            st.write("No citations available.")
        else:
            for i, c in enumerate(citations, start=1):
                txt = c.get("chunk", "")
                meta = c.get("meta", {})
                st.markdown(f"**{i}.** {meta.get('title') or meta.get('url') or 'Context chunk'}")
                with st.popover(f"View snippet {i}"):
                    st.write(txt[:1500])

    st.success("Done!")

# Quick tools for restore/view last run if cloud is on
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Rerun"):
        st.rerun()
with col2:
    if is_configured():
        if st.button("📥 Load last saved brief"):
            data = load_brief(st.session_state.topic_id)
            if data:
                st.markdown(data.get("brief", ""))
            else:
                st.info("No saved brief found for this session.")
