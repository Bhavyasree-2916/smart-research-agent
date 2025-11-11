from __future__ import annotations

import json
import os
from typing import List, Dict
from openai import OpenAI

# Load model name and API key from environment variables (from Streamlit Secrets)
MODEL_SMALL = os.getenv("MODEL_SMALL", "gpt-4o-mini")
OPEN_API_KEY = os.getenv("OPEN_API_KEY") or os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPEN_API_KEY)

def generate_quiz(brief_text: str, n: int = 5) -> List[Dict]:
    """
    Generates n multiple-choice questions (MCQs) from a given text.
    Each question has 4 options and one correct answer.
    Returns a list of dicts like:
    [{"question": "...", "options": ["A","B","C","D"], "answer": "B"}]
    """
    if not brief_text or not brief_text.strip():
        return []

    prompt = f"""
Create {n} multiple-choice questions (4 options each) based ONLY on this text.

=== TEXT START ===
{brief_text}
=== TEXT END ===

Return STRICT JSON only, like this:
[
  {{"question": "What is X?", "options": ["A", "B", "C", "D"], "answer": "B"}}
]
"""

    try:
        resp = client.chat.completions.create(
            model=MODEL_SMALL,
            messages=[
                {"role": "system", "content": "You are a careful quiz maker. Output JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )
        txt = (resp.choices[0].message.content or "").strip()
        return json.loads(txt)
    except Exception as e:
        print("Quiz generation error:", repr(e))
        return []
