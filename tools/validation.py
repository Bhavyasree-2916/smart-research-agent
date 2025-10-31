# tools/validation.py
import re
from textstat import flesch_kincaid_grade

def validate_brief(brief_text: str, citations: list):
    """Return metrics + pass/fail for your brief."""
    word_count = len(re.findall(r"\b\w+\b", brief_text or ""))
    unique_domains = len({c.get("domain") for c in (citations or []) if c.get("domain")})
    try:
        readability = round(float(flesch_kincaid_grade(brief_text or "")), 2)
    except Exception:
        readability = 99.0  # if text too short, etc.

    passed = (250 <= word_count <= 350) and (unique_domains >= 3) and (readability <= 10)
    return {
        "word_count": word_count,
        "unique_domains": unique_domains,
        "readability_grade": readability,
        "passed": passed
    }
