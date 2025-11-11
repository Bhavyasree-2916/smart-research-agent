from __future__ import annotations
import os
import sys
import json
import traceback
import streamlit as st
from typing import List, Dict, Any

# ---------- PATH FIX ----------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------- SAFE IMPORTS ----------
try:
    from agents.researcher import research_from_web
except Exception:
    st.error("❌ Could not import researcher agent.")
    st.code(traceback.format_exc())
    research_from_web = lambda *a, **kw: []

try:
    from agents.synthesizer import synthesize_brief
except Exception:
    st.error("❌ Could not import synthesizer agent.")
    st.code(traceback.format_exc())
    synthesize_brief = lambda *a, **kw: {"brief": "", "citations": []}

try:
    from agents.quiz import generate_quiz
except Exception:
    st.error("❌ Could not import quiz generator.")
    st.code(traceback.format_exc())
    generate_quiz = lambda *a, **kw: []

# ---------- KEYS / MODELS ----------
OPEN_API_KEY = os.getenv("OPEN_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL_SMALL = os.getenv("MODEL_SMALL", "gpt-4o-mini")

# ---------- PAGE SETUP ----------
st.set_page_config(page_title="Smart Research Agent", page_icon="🧠", layout="wide")
st.title("🧠 Smart Research → Brief → Quiz Agent")

with st.expander("⚙️ Environment Check", expanded=False):
    st.write("Model:", MODEL_SMALL)
    st.write("OpenAI Key:", "✅ Found" if OPEN_API_KEY else "❌ Missing")

# ---------- MAIN TABS ----------
tab_research, tab_brief, tab_quiz = st.tabs(["🌐 Research", "🧾 Brief", "🧩 Quiz"])

# ============================================
# 🌐 TAB 1 — Research Agent
# ============================================
with tab_research:
    st.header("🌐 Research from Web")
    topic = st.text_input("Enter a topic or question", placeholder="e.g., Impact of AI in healthcare")
    n_sources = st.slider("Number of web sources", 3, 10, 5)

    if st.button("🔍 Search and Summarize"):
        if not topic.strip():
            st.warning("Please enter a topic to research.")
        else:
            with st.spinner("Researching the web..."):
                try:
                    results = research_from_web(topic, n_sources)
                    st.session_state["research_sources"] = results
                    st.session_state["topic_name"] = topic
                except Exception as e:
                    st.error("Research agent failed.")
                    st.code(traceback.format_exc())

    if "research_sources" in st.session_state:
        st.success("✅ Research completed! Sources:")
        for i, src in enumerate(st.session_state["research_sources"], start=1):
            st.markdown(f"**{i}.** {src.get('title', 'Untitled')} — {src.get('url', '')}")

# ============================================
# 🧾 TAB 2 — Synthesize Brief
# ============================================
with tab_brief:
    st.header("🧾 Generate Research Brief")
    topic_name = st.session_state.get("topic_name", "")
    topic_input = st.text_input("Enter topic name", value=topic_name, placeholder="e.g., Impact of AI in healthcare")

    if st.button("🧠 Synthesize Brief"):
        with st.spinner("Synthesizing summary and citations..."):
            try:
                sources = st.session_state.get("research_sources", [])
                if not sources:
                    st.warning("Please run the Research tab first.")
                else:
                    result = synthesize_brief(topic=topic_input, sources=sources)
                    st.session_state["brief"] = result.get("brief", "")
                    st.session_state["citations"] = result.get("citations", [])
                    st.session_state["topic_name"] = topic_input
            except Exception:
                st.error("Brief synthesis failed.")
                st.code(traceback.format_exc())

    if "brief" in st.session_state:
        st.subheader("🧠 Research Brief")
        st.write(st.session_state["brief"])
        if st.session_state.get("citations"):
            st.markdown("**📚 Citations:**")
            for c in st.session_state["citations"]:
                st.markdown(f"- {c}")

# ============================================
# 🧩 TAB 3 — Quiz Generator
# ============================================
with tab_quiz:
    st.header("🧩 Quiz Agent")
    st.write("Generate quiz questions based on your research brief.")

    brief_text = st.text_area(
        "Paste your research brief text below:",
        value=st.session_state.get("brief", ""),
        height=220
    )
    num_q = st.slider("Number of questions", 3, 10, 5)

    if st.button("🎯 Generate Quiz"):
        if not brief_text.strip():
            st.warning("Please provide brief text.")
        else:
            with st.spinner("Generating quiz..."):
                try:
                    quiz = generate_quiz(brief_text, n=num_q)
                    st.session_state["quiz"] = quiz
                except Exception:
                    st.error("Quiz generation failed.")
                    st.code(traceback.format_exc())

    if "quiz" in st.session_state and st.session_state["quiz"]:
        st.success("✅ Quiz generated!")
        for i, q in enumerate(st.session_state["quiz"], 1):
            st.markdown(f"**Q{i}. {q.get('question', '')}**")
            opts = q.get("options", [])
            choice = st.radio(
                f"Choose answer for Q{i}",
                opts,
                index=None,
                key=f"quiz_q{i}",
                label_visibility="collapsed"
            )
            correct = q.get("answer")
            if choice:
                if choice == correct:
                    st.write("✅ Correct!")
                else:
                    st.write(f"❌ Correct answer: **{correct}**")
            st.divider()

        st.download_button(
            "⬇️ Download Quiz JSON",
            data=json.dumps(st.session_state["quiz"], indent=2, ensure_ascii=False),
            file_name="quiz.json",
            mime="application/json"
        )

# ---------- FOOTER ----------
st.caption("Built with ❤️ using Streamlit, OpenAI, and Supabase.")
