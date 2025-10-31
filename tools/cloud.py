# tools/cloud.py
import os
from typing import Optional, Dict, Any
try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = None  # type: ignore

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

_client: Optional["Client"] = None
if SUPABASE_URL and SUPABASE_ANON_KEY and create_client:
    _client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def save_run(topic: str, brief: Dict[str, Any], quiz: Any) -> Optional[Dict[str, Any]]:
    """
    Inserts a row in topics + briefs. Returns IDs for sharing.
    If Supabase isn't configured, returns None.
    """
    if not _client:
        return None
    t = _client.table("topics").insert({"title": topic}).execute().data[0]
    b = _client.table("briefs").insert({
        "topic_id": t["id"],
        "summary_md": brief.get("brief", ""),
        "citations": brief.get("citations", []),
        "quiz": quiz
    }).execute().data[0]
    return {"topic": t, "brief": b}
# tools/cloud.py (add at the bottom)

def is_configured() -> bool:
    return client is not None

def load_brief(brief_id: str):
    """Fetch a single brief row by id. Returns dict or None."""
    if not client: 
        return None
    res = client.table("briefs").select("*").eq("id", brief_id).execute()
    data = res.data
    return data[0] if data else None
