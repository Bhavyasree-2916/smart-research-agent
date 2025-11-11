# agents/quiz.py
from __future__ import annotations
import re, json, random
from typing import List, Dict
from collections import Counter
from config import OPENAI_API_KEY, MODEL_SMALL

STOP = {
    "the","a","an","and","or","but","if","then","is","are","was","were","be","been","being",
    "to","of","in","on","for","by","with","as","at","from","that","this","these","those",
    "it","its","their","his","her","you","your","we","our","they","them","i","me","my",
    "not","no","yes","very","more","most","such","also","can","may","might","should","could"
}

def _clean(md: str) -> str:
    md = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    return re.sub(r"\s+", " ", md).strip()

def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p for p in parts if len(p.split()) >= 6]

def _top_keywords(text: str, k: int = 60) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
    cnt = Counter(w for w in words if w not in STOP)
    return [w for w,_ in cnt.most_common(k)]

def _json_unique(items: List[Dict]) -> List[Dict]:
    seen, out = set(), []
    for it in items:
        key = json.dumps(it, sort_keys=True)
        if key in seen: continue
        seen.add(key); out.append(it)
    return out

# ---- LLM path (best quality) ----
def _llm_quiz(brief_md: str, topic: str, n: int) -> List[Dict]:
    if not OPENAI_API_KEY:
        return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        system = ("Create concise MCQs strictly grounded in the BRIEF. "
                  "No generic or study-skill questions.")
        user = (
            f"TOPIC: {topic}\n\nBRIEF:\n{brief_md}\n\n"
            f"Create EXACTLY {n} MCQs. Each item must be an object with keys "
            "q, options (4 strings), answer_index (0-3), explanation. "
            "Respond with ONLY a JSON array."
        )
        r = client.chat.completions.create(
            model=MODEL_SMALL or "gpt-4o-mini",
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            temperature=0.2,
        )
        data = json.loads(r.choices[0].message.content.strip())
        good = []
        for it in data:
            if isinstance(it, dict) and {"q","options","answer_index"} <= set(it) and len(it["options"]) == 4:
                good.append(it)
        return good[:n]
    except Exception:
        return []

# ---- Fallback: build MCQs directly from the brief (no LLM) ----
def _cloze_from_brief(brief_md: str, n: int) -> List[Dict]:
    text = _clean(brief_md)
    sents = _sentences(text)
    keys  = _top_keywords(text)
    random.shuffle(sents)
    out, used_answers = [], set()

    for s in sents:
        s_low = s.lower()
        # pick a keyword that appears in this sentence and is not used yet
        cand = [k for k in keys if k in s_low and len(k) >= 4 and k not in used_answers]
        if not cand: 
            continue
        correct = cand[0]
        masked  = re.sub(re.escape(correct), "____", s, flags=re.IGNORECASE, count=1)

        # build distractors from other keywords of similar length
        pool = [k for k in keys if k != correct and abs(len(k)-len(correct)) <= 3]
        random.shuffle(pool)
        distractors = []
        for k in pool:
            if k not in distractors:
                distractors.append(k)
            if len(distractors) == 3: break
        while len(distractors) < 3:
            variant = correct + random.choice(["s","ing","ness","ity","ism"])
            if variant not in distractors:
                distractors.append(variant)

        options = [correct] + distractors
        random.shuffle(options)
        out.append({
            "q": masked,
            "options": options,
            "answer_index": options.index(correct),
            "explanation": f"The blank is '{correct}'."
        })
        used_answers.add(correct)
        if len(out) >= n:
            break
    return out

def _presence_from_brief(brief_md: str, needed: int) -> List[Dict]:
    text = _clean(brief_md)
    keys = [k for k in _top_keywords(text) if len(k) >= 4]
    out = []
    i = 0
    while len(out) < needed and i + 4 <= len(keys):
        correct = keys[i]
        distractors = keys[i+1:i+4]
        i += 4
        options = [correct] + distractors
        random.shuffle(options)
        out.append({
            "q": "Which of the following terms is explicitly mentioned in the brief?",
            "options": options,
            "answer_index": options.index(correct),
            "explanation": f"'{correct}' appears in the brief."
        })
    return out

def make_quiz(brief_md: str, topic: str = "", n: int = 5) -> List[Dict]:
    # 1) Try LLM
    qs = _llm_quiz(brief_md, topic or "general", n)

    # 2) Fallbacks from the brief itself
    if len(qs) < n:
        qs += _cloze_from_brief(brief_md, n - len(qs))
    if len(qs) < n:
        qs += _presence_from_brief(brief_md, n - len(qs))

    # 3) Deduplicate and cap
    qs = _json_unique(qs)[:n]

    # 4) Last resort: if all stems identical (rare), randomize stems
    if len({q["q"] for q in qs}) == 1:
        for idx, q in enumerate(qs):
            q["q"] = q["q"].replace("____", f"____ ({idx+1})")
    return qs
