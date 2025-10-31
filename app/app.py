# app/app.py

# --- make sure Python can import ../agents and ../tools ---
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import uuid
import streamlit as st

# project imports
from agents.planner import plan_queries
from agents.researcher import research_from_web
from agents.synthesizer import synthesize_brief
from agents.quiz import make_quiz
from tools.cloud import save_run  # returns None if Supabase not configured
from tools.validation import validate_brief
from tools.cloud import save_run, is_configured, load_brief

# ------------------ UI CONFIG ------------------
st.set_page_config(page_title="Smart Research Agent", page_icon="🧠", layout="centered")
st.markdown(
    "<h2 style='text-align:center;'>🧠 Smart Research → Brief → Quiz Agent</h2>",
    unsafe_allow_html=True,
)
st.caption("Enter a topic. The agent plans queries, researches Wikipedia, writes a brief, and makes a quiz.")
# --- Share view: open a saved brief via URL param (?brief_id=...)
qp = st.query_params
if "brief_id" in qp and is_configured():
    bid = qp["brief_id"][0]
    data = load_brief(bid)
    if data:
        st.success("Loaded shared brief ✅")
        st.subheader("📌 Brief")
        st.markdown(data["summary_md"] or "")
        st.subheader("🔗 Citations")
        cites = data.get("citations") or []
        if not cites:
            st.caption("No citations available.")
        else:
            for c in cites:
                url = c.get("url","")
                dom = c.get("domain","")
                if url:
                    st.markdown(f"- [{dom or url}]({url})")
        st.info("Tip: Replace the brief_id in the URL to load another result.")
        st.stop()  # don't render input UI on this share page
with st.sidebar:
    st.header("ℹ️ About")
    st.write(
        "Multi-agent research app:\n"
        "• Planner → sub-queries\n"
        "• Researcher → fetch & chunk\n"
        "• Synthesizer → brief with citations\n"
        "• Quiz → 5 MCQs"
    )
    st.divider()
    st.subheader("Share")
    st.write("After a run is saved, use the brief link shown in the results.")
    st.caption("Tip: You can also open a saved brief with `?brief_id=<ID>`.")

# ------------------ STATE ------------------
if "results" not in st.session_state:
    st.session_state.results = None

# ------------------ INPUTS ------------------
topic = st.text_input("Topic", value="LLM agents in healthcare")
col1, col2 = st.columns([1, 1])
with col1:
    per_query = st.slider("Sources per subquery", 1, 3, 1)
with col2:
    run_btn = st.button("Run Agent", type="primary")

# ------------------ PIPELINE ------------------
if run_btn and topic.strip():
    # A stable UUID derived from the topic text (so re-runs hit same vector collection)
    topic_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, topic))

    with st.status("Planning…", expanded=False) as s:
        # 1) PLAN
        
        subqs = plan_queries(topic)
        st.write(subqs)

        # 2) RESEARCH (fetch + chunk + upsert to vector store)
        s.update(label="Researching sources…")
        sources = research_from_web(subqs, per_query=per_query, topic_id=topic_id, topic=topic)


        # 3) SYNTHESIZE (RAG → brief + citations)
        s.update(label="Synthesizing brief…")
        brief = synthesize_brief(topic, sources, topic_id=topic_id)  # dict: {brief, citations}

        # 4) QUIZ
        s.update(label="Generating quiz…")
        quiz = make_quiz(brief["brief"])
        
        metrics = validate_brief(brief["brief"], brief["citations"])

        st.subheader("✅ Validation")
        colA, colB, colC = st.columns(3)
        colA.metric("Word count", metrics["word_count"], "target 250–350")
        colB.metric("Unique domains", metrics["unique_domains"], "≥ 3")
        colC.metric("Readability (FK grade)", metrics["readability_grade"], "≤ 10")

        if metrics["passed"]:
            st.success("Brief passed quality checks.")
        else:
            st.warning("Brief failed quality checks (length/sources/readability). "
               "Try increasing 'sources per subquery' or a broader topic.")
    # Simple retry: ask for more sources and rerun synth
            more_sources = research_from_web(subqs, per_query=max(2, per_query + 1),
                                     topic_id=topic_id, topic=topic)
            sources = sources + more_sources
            brief = synthesize_brief(topic, sources, topic_id=topic_id)
            metrics = validate_brief(brief["brief"], brief["citations"])
        if not metrics["passed"]:
            quiz = make_quiz(brief["brief"])

        # 5) SAVE to session
        st.session_state.results = {
            "topic": topic,
            "topic_id": topic_id,
            "subqs": subqs,
            "sources": sources,
            "brief": brief,
            "quiz": quiz,
        }

        # 6) OPTIONAL: Save to Supabase (only if SUPABASE_URL/KEY set)
        saved = save_run(topic, brief, quiz)
        if saved:
            st.success("Saved to Supabase ✅")
            st.caption(f"Topic ID: {saved['topic']['id']}")
            st.caption(f"Brief ID: {saved['brief']['id']}")
        else:
            st.info("Skipping cloud save (Supabase not configured).")

        s.update(label="Done!", state="complete")

# ------------------ OUTPUT RENDER ------------------
# ------------------ OUTPUT RENDER ------------------
res = st.session_state.results
if res:
    st.subheader("Results")

    with st.expander("📌 Brief", expanded=True):
        st.markdown(res["brief"]["brief"])

    with st.expander("🔗 Citations", expanded=True):
        cites = res["brief"]["citations"]
        if cites:
            for c in cites:
                url = c.get("url", "")
                dom = c.get("domain", "")
                if url:
                    st.markdown(f"- [{dom or 'source'}]({url})")
        else:
            st.caption("No citations available.")

    with st.expander("📝 Quiz", expanded=True):
        score = 0
        for i, q in enumerate(res["quiz"]):
            st.markdown(f"**Q{i+1}. {q['q']}**")
            choice = st.radio("", q["options"], key=f"q{i}", index=None, horizontal=False)
            if choice is not None:
                correct = q["options"][q["answer_index"]]
                if choice == correct:
                    score += 1
                st.caption(f"Answer: **{correct}** — {q.get('explanation', '')}")
            st.divider()
        st.success(f"Your score (so far): {score} / {len(res['quiz'])}")
