# tools/cloud.py
import os
from supabase import create_client

def is_configured():
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))

def _client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

def save_run(topic_title, brief, quiz):
    if not is_configured():
        return None
    sb = _client()

    topic = (sb.table("topics")
               .insert({"title": topic_title})
               .select("id,title")
               .single()
               .execute()).data

    brief_row = (sb.table("briefs")
                   .insert({
                       "topic_id": topic["id"],
                       "summary_md": brief.get("brief",""),
                       "citations": brief.get("citations", [])
                   })
                   .select("id,topic_id")
                   .single()
                   .execute()).data

    quiz_row = (sb.table("quizzes")
                  .insert({
                      "topic_id": topic["id"],
                      "questions": quiz
                  })
                  .select("id,topic_id")
                  .single()
                  .execute()).data

    return {"topic": topic, "brief": brief_row, "quiz": quiz_row}
