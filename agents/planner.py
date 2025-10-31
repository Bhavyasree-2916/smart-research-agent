def plan_queries(topic: str):
    topic = topic.strip()
    base = [
        f"{topic} definition and overview",
        f"{topic} applications and use cases",
        f"{topic} challenges or limitations",
        f"{topic} evaluation metrics or comparisons",
    ]
    # keep it 3–5 items, unique
    seen, out = set(), []
    for q in base:
        if q.lower() not in seen:
            seen.add(q.lower()); out.append(q)
    return out[:5]
