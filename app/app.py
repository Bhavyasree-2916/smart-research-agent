from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
from typing import List, Dict, Any

# --- Fix import path for Streamlit Cloud ---
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# --- Import local agent modules ---
from agents.researcher import research_from_web
from agents.synthesizer import synthesize_brief
from agents.quiz import generate_quiz

# -----------------------------
# Streamlit Page Configuration
# -----------------------------
st.set_page_config(
    page_title="Smart Research → Brief → Quiz Agent",
    layout="centered",
    page_icon="🧠",
)

# App Header
st.title("🧠 Smart Research → Brief → Quiz Agent")
st.markdown("Enter a topic to research, summarize it, and generate a quiz — all in one page!")

# --- INPUT SECTION ---
topic = st.text_input("Enter the topic to research:")
n_sources = st.slider("Number of web sources", 1, 10, 5)
n_questions = st.slider("Number of quiz questions", 1, 10, 5)

# --- RUN AGENT BUTTON ---
if st.button("Run Research Agent"):
    if not topic.strip():
        st.error("⚠️ Please enter a topic name first.")
    else:
        with st.spinner("🔍 Researching..."):
            try:
                # Step 1: Research from the web
                research_results = research_from_web(topic, n_sources)
                if not research_results:
                    st.warning("No web results found. Try a different topic.")
                else:
                    st.success(f"✅ Research complete! Collected {len(research_results)} sources.")
                    for i, r in enumerate(research_results, start=1):
                        st.markdown(f"**{i}. {r.get('title', 'Untitled')}**")
                        st.markdown(r.get('url', ''))
                        st.write(r.get('snippet', ''))
                        st.divider()

                    # Step 2: Generate research brief
                    with st.spinner("🧠 Synthesizing research brief..."):
                        brief, citations = synthesize_brief(topic, research_results)
                        st.subheader("📄 Research Brief")
                        st.write(brief)

                        st.subheader("🔗 Citations")
                        if citations:
                            for c in citations:
                                st.markdown(f"- {c}")
                        else:
                            st.write("No citations available.")

                    # Step 3: Generate quiz
                    with st.spinner("❓ Generating quiz..."):
                        quiz = generate_quiz(topic, n_questions)
                        st.subheader("📝 Generated Quiz")
                        if quiz:
                            for i, q in enumerate(quiz, start=1):
                                st.markdown(f"**Q{i}. {q['question']}**")
                                for opt in q["options"]:
                                    st.write(f"- {opt}")
                                st.markdown(f"**Answer:** {q['answer']}")
                                st.divider()
                        else:
                            st.warning("No quiz generated. Try another topic.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# Footer
st.markdown("---")
st.caption("Built with ❤️ using Streamlit, OpenAI, and Supabase.")
