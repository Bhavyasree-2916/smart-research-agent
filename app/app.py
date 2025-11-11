from __future__ import annotations
import os
import sys
import traceback
import json
import streamlit as st
from typing import List, Dict, Any

# ---------- PATH FIX ----------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------- IMPORTS ----------
try:
    from agents.researcher import research_from_web
    from agents.synthesizer import synthesize_brief
    from agents.quiz import generate_quiz
except Exception as e:
    st.error("❌ Error importing agents.")
    st.code(traceback.format_exc())

# ---------- PAGE SETUP ----------
st.set_page_config(page_title="Smart Research Agent", page_icon="🧠", layout="wide")

st.title("🧠 Smart Research → Brief → Quiz Agent")
st.write("Enter a topic to research, generate a brief, and create a quiz — all in one place.")

# ---------- INPUT CONTROLS ----------
topic = st.text_input("🎯 Enter your topic:", placeholder="e.g., Impact of AI in healthcare")
num_sources = st.slider("🔎 Number of sources to collect", 3, 10, 5)
num_questions = st.slider("🧩 Number of quiz questions", 3, 10, 5)

# ---------- RUN BUTTON ----------
if st.button("🚀 Run Agent"):
    if not topic.strip():
        st.warning("Please enter a valid topic.")
    else:
        try:
            # -------- STEP 1: Research --------
            with st.spinner("🔍 Researching topic from the web..."):
                sources = research_from_web(topic, num_sources=num_sources)
                st.session_state["sources"] = sources
            st.success("✅ Research completed successfully!")

            # -------- STEP 2: Synthesize Brief --------
            with st.spinner("🧠 Synthesizing research brief..."):
                result = synthesize_brief(topic=topic, sources=sources)
                brief = result.get("brief", "")
                citations = result.get("citations", [])
                st.session_state["brief"] = brief
                st.session_state["citations"] = citations

            st.subheader("🧾 Research Brief")
            st.write(brief)

            if citations:
                st.markdown("**📚 References:**")
                for c in citations:
                    st.markdown(f"- {c}")

            # -------- STEP 3: Generate Quiz --------
            with st.spinner("🎯 Generating quiz questions..."):
                quiz = generate_quiz(brief, n=num_questions)
                st.session_state["quiz"] = quiz

            st.subheader("🧩 Quiz Questions")
            for i, q in enumerate(quiz, start=1):
                st.markdown(f"**Q{i}. {q.get('question', '')}**")
                options = q.get("options", [])
                answer = q.get("answer", "")
                selected = st.radio(
                    f"Select your answer for Q{i}",
                    options,
                    key=f"q{i}",
                    label_visibility="collapsed",
                )
                if selected:
                    if selected == answer:
                        st.success("✅ Correct!")
                    else:
                        st.error(f"❌ Correct Answer: {answer}")

            # -------- DOWNLOAD BUTTON --------
            st.download_button(
                "⬇️ Download Results (JSON)",
                data=json.dumps({
                    "topic": topic,
                    "brief": brief,
                    "citations": citations,
                    "quiz": quiz
                }, indent=2),
                file_name=f"{topic.replace(' ', '_')}_results.json",
                mime="application/json"
            )

        except Exception as e:
            st.error("🚨 Research agent failed. See details below:")
            st.code(traceback.format_exc())

# ---------- FOOTER ----------
st.caption("Built with ❤️ using Streamlit, OpenAI, and Supabase.")
ss