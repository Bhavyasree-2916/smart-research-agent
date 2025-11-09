# app_gradio.py
import os, sys
sys.path.append(os.path.abspath("."))  # so we can import agents/ tools/

import gradio as gr
from agents.planner import plan_queries
from agents.researcher import research_from_web
from agents.synthesizer import synthesize_brief
from agents.quiz import make_quiz
from tools.validation import validate_brief

def run_agent(topic: str, per_query: int):
    if not topic.strip():
        return "Please enter a topic.", "", ""

    # 1) Plan
    subqs = plan_queries(topic)

    # 2) Research (+ topic fallback inside your researcher)
    sources = research_from_web(subqs, per_query=per_query, topic_id=topic, topic=topic)

    # 3) Synthesize brief + citations
    brief = synthesize_brief(topic, sources, topic_id=topic)
    summary_md = brief["brief"]
    cites = brief.get("citations", [])

    # 4) Validate
    metrics = validate_brief(summary_md, cites)
    val_md = (
        f"**Validation**  \n"
        f"- Word count: **{metrics['word_count']}** (target 250–350)  \n"
        f"- Unique domains: **{metrics['unique_domains']}** (≥3)  \n"
        f"- FK Grade: **{metrics['readability_grade']}** (≤10)  \n"
        f"- Passed: **{metrics['passed']}**"
    )

    # 5) Quiz (render as markdown for simplicity)
    quiz = make_quiz(summary_md)
    quiz_md = []
    for i, q in enumerate(quiz, 1):
        opts = "\n".join([f"  - {o}" for o in q["options"]])
        quiz_md.append(f"**Q{i}. {q['q']}**\n{opts}\n<small>Answer: {q['options'][q['answer_index']]}</small>\n")
    quiz_md = "\n\n".join(quiz_md)

    # Citations as markdown
    if cites:
        cite_md_lines = [f"- [{c.get('domain') or 'source'}]({c.get('url','')})" for c in cites if c.get("url")]
        cite_md = "\n".join(cite_md_lines)
    else:
        cite_md = "_No citations available._"

    # Add planned queries and fetched count for transparency
    header = f"**Planned sub-queries:** {len(subqs)}  \n**Fetched sources:** {len(sources)}"
    out_summary = f"{header}\n\n---\n\n{summary_md}"

    return out_summary, cite_md, f"{val_md}\n\n---\n\n{quiz_md}"

with gr.Blocks() as demo:
    gr.Markdown("# 🧠 Smart Research → Brief → Quiz (Gradio)")
    with gr.Row():
        topic = gr.Textbox(label="Topic", value="LLM agents in healthcare")
        per_query = gr.Slider(1, 3, value=2, step=1, label="Sources per subquery")
    run_btn = gr.Button("Run Agent")
    brief = gr.Markdown()
    citations = gr.Markdown()
    validation_quiz = gr.Markdown()

    run_btn.click(run_agent, [topic, per_query], [brief, citations, validation_quiz])

if __name__ == "__main__":
    demo.launch(share=True)  # local + temporary public URL
