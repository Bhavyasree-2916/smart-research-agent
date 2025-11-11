# app/app.py
# Smart Research → Brief → Quiz (Streamlit)
# Safe to run on Streamlit Cloud. Optional Supabase is handled gracefully.

from agents.researcher import research_from_web
from agents.synthesizer import synthesize_brief
from agents.quiz import generate_quiz
from __future__ import annotations

import os,sys
import uuid
from typing import Dict, List, Any

import streamlit as st

# ========= Optional cloud (Supabase) =========
# If tools.cloud is not present or not configured, we fall back to no-ops.
try:
    from tools.cloud import save_run, is_configured, load_brief  # type: ignore
except Exception:
    def save_run(*args, **kwargs):
        return None
    def is_configured() -> bool:
        return False
    def load_brief(*args, **kwargs):
        return None

# ========= Agents & tools (required) =========
# These should exist in your repo.
from agents.researcher import research_from_web  # -> List[Dict]
from agents.synthesizer import synthesize_brief   # -> Dict[brief, citations]
from agents.quiz import generate_quiz             # -> List[Dict]
# Optional readability validation (won't fail if missing)
try:
    from tools.validation import flesch_kincaid_grade
except Exception:
    def flesch_kincaid_grade(text: str) -> float:
        return 0.0


# ========= Page config =========
st.set_page_config(
    page_title="Smart Research Agent",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Smart Research → Brief → Quiz Agent")

with st.expander("About", expanded=False):
    st.markdown(
        "- Enter a topic. The agent plans sub-queries, researches Wikipedia/web, writes a brief, and makes a quiz.\n"
        "- Use **Sources per subquery** to control how many citations are pulled for each subtopic.\n"
        "- If Supabase is configured in *Manage app → Settings → Secrets*, runs will be saved."
    )

# ========= Sidebar controls =========
with st.sidebar:
    st.header("Controls")
    topic = st.text_input(
        "Topic",
        placeholder="e.g., LLM agents in healthcare",
        value=st.session_state.get("last_topic", ""),
    )
    sources_per_subquery = st.slider(
        "Sources per subquery",
        min_value=1, max_value=10, value=3, step=1,
        help="How many sources to fetch per subtopic"
    )
    num_quiz_questions = st.slider(
        "Quiz questions",
        min_value=3, max_value=10, value=5, step=1
    )

    # Session-scoped topic_id
    if "topic_id" not in st.session_state or st.session_state.get("last_topic") != topic:
        st.session_state.topic_id = str(uuid.uuid4())
        st.session_state.last_topic = topic
    topic_id = st.session_state.topic_id

    st.caption(f"Topic ID: `{topic_id}`")
    run_btn = st.button("Run Agent", type="primary", use_container_width=True)

# ========= Guard clauses =========
if run_btn and not topic.strip():
    st.warning("Please enter a topic and click **Run Agent**.")
    st.stop()

# ========= Main run =========
if run_btn and topic.strip():
    # Step 1: Research
    with st.spinner("🔎 Researching…"):
        try:
            sources: List[Dict[str, Any]] = research_from_web(
                topic=topic.strip(),
                n_sources=sources_per_subquery
            )
        except Exception as e:
            st.error(f"Research step failed: {e}")
            st.stop()

    # Show sources
    with st.expander("Sources", expanded=False):
        if not sources:
            st.info("No sources returned.")
        else:
            for i, s in enumerate(sources, 1):
                title = s.get("title") or "Untitled"
                url = s.get("url") or ""
                st.markdown(f"**{i}. {title}**  \n{url}")

    # Step 2: Synthesize brief
    with st.spinner("🧵 Synthesizing brief…"):
        try:
            result: Dict[str, Any] = synthesize_brief(
                topic=topic.strip(),
                sources=sources,
                topic_id=topic_id,
                k=15,  # retrieval size; your synthesizer can ignore if unused
            )
        except Exception as e:
            st.error(f"Synthesis step failed: {e}")
            st.stop()

    brief: str = (result or {}).get("brief", "").strip()
    citations: List[Dict[str, Any]] = (result or {}).get("citations", [])

    if not brief:
        st.error("No brief produced. Check your OpenAI key and network, then try again.")
        st.stop()

    # Optional: readability
    grade = 0.0
    try:
        grade = flesch_kincaid_grade(brief)
    except Exception:
        pass

    st.subheader("📝 Brief")
    st.write(brief)
    st.caption(f"Readability (Flesch-Kincaid grade): {grade:.1f}")

    st.subheader("🔗 Citations")
    if citations:
        for i, c in enumerate(citations, 1):
            label = c.get("title") or c.get("source") or "Source"
            url = c.get("url") or ""
            st.markdown(f"{i}. **{label}**  \n{url}")
    else:
        st.info("No citations returned by the synthesizer.")

    # Step 3: Quiz
    with st.spinner("🧪 Generating quiz…"):
        try:
            quiz: List[Dict[str, Any]] = generate_quiz(
                brief_text=brief,
                n=num_quiz_questions
            )
        except Exception as e:
            st.error(f"Quiz step failed: {e}")
            st.stop()

    st.subheader("❓ Quiz")
    if not quiz:
        st.info("No quiz generated.")
    else:
        # Render MCQs, ensure unique questions
        asked = set()
        for idx, q in enumerate(quiz, 1):
            qtext = (q.get("question") or "").strip()
            if not qtext or qtext.lower() in asked:
                continue
            asked.add(qtext.lower())

            with st.container(border=True):
                st.markdown(f"**Q{idx}. {qtext}**")
                options = q.get("options") or []
                key = f"q_{idx}_{uuid.uuid4().hex[:6]}"
                st.radio(" ", options, key=key, label_visibility="collapsed")

    # Optional: save to Supabase (if configured)
    if is_configured():
        try:
            save_run(
                topic_id=topic_id,
                title=topic.strip(),
                brief=brief,
                citations=citations,
                sources=sources,
                quiz=quiz,
            )
            st.success("Run saved to Supabase.")
        except Exception:
            st.warning("Supabase configured but save failed. Check your credentials/logs.")

# ========= Footer =========
st.divider()
st.caption(
    "Tip: You can open a saved brief (when Supabase is configured) via its Topic ID."
)
load_col1, load_col2 = st.columns([3, 1])
with load_col1:
    load_id = st.text_input("Load brief by Topic ID", placeholder="paste a topic_id")
with load_col2:
    load_btn = st.button("Load")
if load_btn and load_id.strip() and is_configured():
    data = load_brief(load_id.strip())
    if not data:
        st.error("No record found for that Topic ID.")
    else:
        st.success("Loaded!")
        st.write(data.get("brief", ""))
