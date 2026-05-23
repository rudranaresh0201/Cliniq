import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.llm.router import complete, parse_json

CONTRADICTION_PROMPT = """Check if this medical AI response contradicts what the patient stated.

Patient stated: {patient_query}
AI Response conditions: {conditions}

Look for contradictions like:
- Patient denies symptom but condition requires it as a defining feature
- Age-inappropriate conditions (e.g. Alzheimer's in a 15-year-old)
- Gender-inappropriate conditions
- Duration mismatch (e.g. acute condition suggested for chronic symptom)

Return ONLY JSON:
{{
  "contradictions_found": <bool>,
  "contradictions": ["<contradiction 1>"],
  "safe_to_return": <bool>
}}"""


async def check_contradictions(query: str, result: dict) -> dict:
    """
    Catches cases where the generated answer contradicts the patient's stated information.
    E.g. patient says 'no rash' but top condition is dengue with rash as defining feature.
    """
    conditions_str = str([
        {"name": c["name"], "confidence": c["confidence"]}
        for c in result.get("conditions", [])[:3]
    ])

    try:
        raw, _ = await complete(
            CONTRADICTION_PROMPT.format(
                patient_query=query[:500],
                conditions=conditions_str,
            ),
            temperature=0.1,
            max_tokens=200,
        )
        return parse_json(raw)
    except Exception:
        return {"contradictions_found": False, "safe_to_return": True, "contradictions": []}
