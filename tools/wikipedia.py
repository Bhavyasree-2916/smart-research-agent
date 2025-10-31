import requests, re, time

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "SmartResearchAgent/1.0 (student project; contact: youremail@example.com)"
}

def _retry_get(params, attempts=3, sleep=0.8):
    for i in range(attempts):
        r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=20)
        if r.status_code in (429, 502, 503):
            time.sleep(sleep); continue
        r.raise_for_status()
        return r
    return None

def search_wikipedia(query: str, limit: int = 3):
    """
    Try the 'search' endpoint first, then fall back to 'opensearch'.
    We also trim long queries.
    """
    q = " ".join(query.split())[:120]

    # 1) 'search' endpoint (more reliable)
    params = {
        "action": "query",
        "list": "search",
        "srsearch": q,
        "srlimit": limit,
        "format": "json"
    }
    r = _retry_get(params)
    if r is not None:
        data = r.json().get("query", {}).get("search", [])
        titles = [i["title"] for i in data]
        if titles:
            return [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in titles]

    # 2) Fallback: 'opensearch'
    params = {
        "action": "opensearch",
        "search": q,
        "limit": limit,
        "namespace": 0,
        "format": "json",
    }
    r = _retry_get(params)
    if r is not None:
        data = r.json()
        titles = data[1] if isinstance(data, list) and len(data) >= 2 else []
        if titles:
            return [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in titles]

    return []  # nothing found

def read_wikipedia_page(url: str, max_chars: int = 4000):
    title = url.split("/wiki/")[-1].replace("_", " ")
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "titles": title,
        "format": "json",
        "redirects": 1,
    }
    r = _retry_get(params)
    if r is None:
        return ""
    pages = r.json()["query"]["pages"]
    text = next(iter(pages.values())).get("extract", "")
    text = re.sub(r"\n{2,}", "\n\n", text).strip()
    return text[:max_chars]
