import os

def _maybe_client():
    """Create Supabase client if secrets exist."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        print("⚠️ Supabase client not configured:", e)
        return None


def is_configured():
    """Return True if Supabase is properly configured."""
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))


def save_run(run_data: dict):
    """Save a run record to Supabase (if configured)."""
    client = _maybe_client()
    if not client:
        return None
    try:
        client.table("runs").insert(run_data).execute()
    except Exception as e:
        print("⚠️ Supabase insert failed:", e)


def load_brief(topic_id: str):
    """Load a brief record from Supabase (if configured)."""
    client = _maybe_client()
    if not client:
        return None
    try:
        result = client.table("briefs").select("*").eq("topic_id", topic_id).execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        print("⚠️ Supabase fetch failed:", e)
        return None
