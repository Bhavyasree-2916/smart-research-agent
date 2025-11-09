import os, json, sqlite3, uuid, math
import numpy as np
from typing import List, Dict, Any, Tuple
from config import EMBEDDING_MODEL, OPENAI_API_KEY
from openai import OpenAI

DB_PATH = os.environ.get("RAG_DB_PATH", "store.sqlite3")
client = OpenAI(api_key=OPENAI_API_KEY)

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS docs(
            id TEXT PRIMARY KEY,
            topic_id TEXT,
            text TEXT,
            meta TEXT,
            embedding TEXT  -- store as JSON list for portability
        )
    """)
    conn.commit()
    return conn

def embed(texts: List[str]) -> List[List[float]]:
    # batch to be polite
    out = []
    batch = 50
    for i in range(0, len(texts), batch):
        part = texts[i:i+batch]
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=part)
        out.extend([d.embedding for d in resp.data])
    return out

def upsert_chunks(topic_id: str, texts: List[str], metadatas: List[Dict[str,Any]]) -> None:
    if not texts: return
    embs = embed(texts)
    with _conn() as c:
        for t, m, e in zip(texts, metadatas, embs):
            c.execute(
                "INSERT OR REPLACE INTO docs(id, topic_id, text, meta, embedding) VALUES(?,?,?,?,?)",
                (str(uuid.uuid4()), topic_id, t, json.dumps(m or {}), json.dumps(e))
            )
        c.commit()

def _cos(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a); nb = np.linalg.norm(b)
    if na == 0 or nb == 0: return 0.0
    return float(np.dot(a, b) / (na * nb))

def query(topic_id: str, text: str, k: int = 5) -> List[Dict[str,Any]]:
    q = embed([text])[0]
    qv = np.array(q, dtype=np.float32)

    with _conn() as c:
        rows = c.execute("SELECT text, meta, embedding FROM docs WHERE topic_id = ?", (topic_id,)).fetchall()

    scored: List[Tuple[float, Dict[str,Any]]] = []
    for t, meta_json, emb_json in rows:
        ev = np.array(json.loads(emb_json), dtype=np.float32)
        score = _cos(qv, ev)
        scored.append((score, {"text": t, "meta": json.loads(meta_json or "{}")}))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for s, item in scored[:k]:
        m = item["meta"] or {}
        out.append({
            "text": item["text"],
            "score": s,
            "url": m.get("url", ""),
            "domain": m.get("domain", "")
        })
    return out

# convenience used by your researcher
def upsert_chunks_simple(topic_id: str, chunks: List[Dict[str,Any]]):
    texts = [c["text"] for c in chunks]
    metas = [c.get("meta", {}) for c in chunks]
    upsert_chunks(topic_id, texts, metas)
