from typing import List, Dict
from config import OPENAI_API_KEY, MODEL_SMALL

def make_quiz(brief_text: str) -> List[Dict]:
    if not OPENAI_API_KEY:
        # Simple placeholder quiz if no key
        return [
            {"q":"Which source type is generally most reliable?",
             "options":["Random blog","Peer-reviewed article","Forum post","Tweet"],
             "answer_index":1,"explanation":"Peer-reviewed sources are vetted."}
        ] * 5
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""Create 5 MCQs from this brief. JSON list where each item has:
q, options (exactly 4), answer_index (0-3), explanation (1 sentence).
Brief:
{brief_text}"""
    msg = client.chat.completions.create(
        model=MODEL_SMALL,
        messages=[{"role":"user","content":prompt}],
        temperature=0.2,
        response_format={"type":"json_object"}
    )
    # Some models return a JSON object; normalize to list under "items"
    import json
    raw = msg.choices[0].message.content
    try:
        data = json.loads(raw)
        if isinstance(data, list): return data
        if "items" in data: return data["items"]
        if "quiz" in data: return data["quiz"]
    except Exception:
        pass
    # fallback minimal quiz
    return [
        {"q":"What is a limitation mentioned?",
         "options":["None","Latency","Infinite compute","Guaranteed accuracy"],
         "answer_index":1,"explanation":"Latency is a common constraint."}
    ] * 5
