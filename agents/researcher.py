from tools.wikipedia import search_wikipedia, read_wikipedia_page
from tools.vecstore import upsert_chunks_simple
from urllib.parse import urlparse

def _split(text, size=800, overlap=120):
    out = []
    i = 0
    while i < len(text):
        out.append(text[i:i+size])
        i += size - overlap
    return [s.strip() for s in out if s.strip()]

def _ingest(url, text, topic_id, sources):
    domain = urlparse(url).netloc
    sources.append({"url": url, "domain": domain, "text": text})
    chunks = _split(text)
    payload = [{
        "id": f"{domain}-{i}",
        "text": c,
        "metadata": {"url": url, "domain": domain, "chunk_id": i}
    } for i, c in enumerate(chunks)]
    if payload:
        upsert_chunks(topic_id, payload)

def research_from_web(subqueries, per_query=1, topic_id="default", topic=None):
    sources = []

    # Try each subquery
    for q in subqueries:
        try:
            urls = search_wikipedia(q, limit=per_query)
        except Exception as e:
            print("search error:", e); urls = []
        for url in urls:
            try:
                text = read_wikipedia_page(url)
                if text:
                    _ingest(url, text, topic_id, sources)
            except Exception as e:
                print("read error:", e)

    # Fallback: search the whole topic if nothing found
    if not sources and topic:
        try:
            urls = search_wikipedia(topic, limit=max(2, per_query))
            for url in urls:
                text = read_wikipedia_page(url)
                if text:
                    _ingest(url, text, topic_id, sources)
        except Exception as e:
            print("fallback search error:", e)

    return sources
