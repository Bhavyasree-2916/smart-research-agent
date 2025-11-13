# app/app.py
from __future__ import annotations

import os
import uuid
import streamlit as st
from typing import List, Dict, Tuple, Any

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

# --- Optional vecstore helpers (no-op if absent)
try:
    from tools.vecstore import upsert_chunks_simple, rag_query  # type: ignore
except Exception:
    def upsert_chunks_simple(topic_id: str, chunks: List[Dict[str, Any]]):
        # no-op placeholder for environments without a vector DB
        return None
    def rag_query(topic_id: str, query: str, k: int = 5):
        return []

# --- Local modules (must exist)
# researcher.research_from_web(topic, n_sources) -> list[dict] or list[str]
# synthesizer.synthesize_brief(topic, research_results) -> (brief:str, citations:List[dict|str])
# quiz.generate_quiz(topic, n) -> list[dict]
from agents.researcher import research_from_web           # type: ignore
from agents.synthesizer import synthesize_brief           # type: ignore
# optionally from agents.quiz import generate_quiz

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
        "Enter a topic. The agent plans queries, fetches sources, builds a small vector index, "
        "synthesizes a brief, and shows citations."
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
def _normalize_chunks(chunks) -> List[Dict[str, Any]]:
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
            # treat plain strings as chunk text
            norm.append({"chunk": str(c), "meta": {}})
    return norm

def _unpack_brief(result) -> Tuple[str, List[Any]]:
    """
    Accept (brief, citations) OR {'brief':..., 'citations':...} OR string (brief).
    Return (brief_text, citations_list).
    """
    if result is None:
        return ("", [])
    if isinstance(result, tuple) and len(result) == 2:
        brief, citations = result
    elif isinstance(result, dict):
        brief = result.get("brief") or result.get("summary") or ""
        citations = result.get("citations") or result.get("sources") or []
    elif isinstance(result, str):
        brief = result
        citations = []
    else:
        # unexpected shape - try to be defensive
        try:
            brief = str(result)
        except Exception:
            brief = ""
        citations = []
    # ensure citations is a list
    if citations is None:
        citations = []
    return brief, citations

def _render_citation_item(c) -> str:
    """Return a readable citation string from different shapes."""
    if isinstance(c, str):
        return c
    if isinstance(c, dict):
        # prefer title + url if present
        title = c.get("title") or c.get("meta", {}).get("title") or c.get("meta", {}).get("url")
        url = c.get("url") or c.get("meta", {}).get("url")
        snippet = c.get("snippet") or c.get("chunk") or ""
        if title and url:
            return f"{title} — {url}\n\n{snippet}"
        if title:
            return f"{title}\n\n{snippet}"
        if url:
            return f"{url}\n\n{snippet}"
        return snippet or str(c)
    return str(c)

# ----------------- Main -----------------
if run:
    if not topic.strip():
        st.warning("Please enter a topic.")
        st.stop()

    topic_id = st.session_state.topic_id or str(uuid.uuid4())
    st.session_state.topic_id = topic_id

    # Step 1: research
    with st.expander("1) Researching & collecting sources...", expanded=True):
        with st.spinner("Searching and collecting context…"):
            # researcher should accept (topic, n_sources) and return list[dict] or list[str]
            raw_results = research_from_web(topic, sources_per_subquery)
            chunks = _normalize_chunks(raw_results)
            st.write(f"Collected **{len(chunks)}** chunks.")
            if chunks:
                try:
                    upsert_chunks_simple(topic_id, chunks)
                    st.success("Indexed in vector store.")
                except Exception as e:
                    st.warning(f"Vector index step failed: {e}")

    # Step 2: synthesize - pass the research results (normalized) to synthesizer
    with st.expander("2) Synthesizing brief...", expanded=True):
        with st.spinner("Summarizing from retrieved context…"):
            # call synthesize_brief(topic, research_results) — many implementations expect the research items
            # we pass the normalized chunks (list of dicts)
            try:
                result = synthesize_brief(topic, chunks, topic_id=topic_id)
            except TypeError:
                # fallback if synthesize_brief expects (topic, research_results) without topic_id
                result = synthesize_brief(topic, chunks)

            brief, citations = _unpack_brief(result)

            # Optional cloud save
            try:
                if is_configured():
                    save_run(topic_id=topic_id, topic=topic, brief=brief, citations=citations)
            except Exception as e:
                st.info(f"Cloud save failed: {e}")

            st.subheader("Brief")
            if brief:
                st.markdown(brief)
            else:
                st.info("No brief returned from the synthesizer.")

            grade = flesch_kincaid_grade(brief or "")
            st.caption(f"Readability (Flesch–Kincaid grade): {grade:.1f}")

    # Step 3: citations
    with st.expander("3) Citations (retrieved context)", expanded=False):
        if not citations:
            st.write("No citations available.")
        else:
            for i, c in enumerate(citations, start=1):
                display_text = _render_citation_item(c)
                st.markdown(f"**{i}.** {display_text}")

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
