import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import logging
from backend.llm.router import complete, parse_json

logger = logging.getLogger("cliniq")

TIMELINE_PROMPT = """You are a longitudinal health analyst. Analyze this patient's episode history to detect patterns, trends, and risks.

Patient History (newest first):
{history_text}

Identify:
1. Recurring symptoms or conditions (same complaint appearing 2+ times)
2. Progressive worsening (escalating triage levels over time)
3. Chronic condition signals (repeated episodes suggesting underlying chronic disease)
4. Medication adherence issues (changing medications, repeated drug questions)

Return ONLY a valid JSON object:
{{
  "patterns_detected": ["<pattern description 1>", "<pattern description 2>"],
  "trend": "<worsening|stable|improving>",
  "chronic_risk_flags": ["<risk flag 1>", "<risk flag 2>"],
  "proactive_recommendation": "<one concrete next-step recommendation for the patient>",
  "urgency": "<routine|urgent|immediate>"
}}

Rules:
- patterns_detected may be empty [] if no meaningful patterns exist
- chronic_risk_flags may be empty [] if no signals detected
- proactive_recommendation must be actionable and specific
- Be conservative — only flag patterns you have clear evidence for"""

FALLBACK = {
    "patterns_detected": [],
    "trend": "stable",
    "chronic_risk_flags": [],
    "proactive_recommendation": "Continue monitoring your symptoms and consult a healthcare provider if new concerns arise.",
    "urgency": "routine",
}


def _build_history_text(patient_history: list[dict]) -> str:
    if not patient_history:
        return "No previous episodes recorded."

    lines = []
    for i, ep in enumerate(patient_history[:20]):
        ts = ep.get("timestamp", "unknown date")
        query = ep.get("query", "")[:200]
        triage = ep.get("triage", "UNKNOWN")
        conditions = ", ".join(ep.get("conditions", [])) or "none identified"
        lines.append(
            f"Episode {i+1} [{ts}]\n"
            f"  Triage: {triage}\n"
            f"  Complaint: {query}\n"
            f"  Conditions flagged: {conditions}"
        )

    return "\n\n".join(lines)


async def analyze_timeline(patient_history: list[dict]) -> dict:
    """
    Reason over a patient's episode history and return longitudinal insights.

    Args:
        patient_history: List of episode dicts from get_patient_history().

    Returns:
        Dict with patterns_detected, trend, chronic_risk_flags,
        proactive_recommendation, and urgency.
    """
    if not patient_history:
        return FALLBACK

    history_text = _build_history_text(patient_history)

    try:
        raw, provider = await complete(
            TIMELINE_PROMPT.format(history_text=history_text),
            temperature=0.2,
            max_tokens=600,
        )
        logger.info(json.dumps({"stage": "timeline.provider", "provider": provider}))
        result = parse_json(raw)

        # Normalise and fill defaults
        result.setdefault("patterns_detected", [])
        result.setdefault("trend", "stable")
        result.setdefault("chronic_risk_flags", [])
        result.setdefault("proactive_recommendation", FALLBACK["proactive_recommendation"])
        result.setdefault("urgency", "routine")

        if result.get("trend") not in ("worsening", "stable", "improving"):
            result["trend"] = "stable"
        if result.get("urgency") not in ("routine", "urgent", "immediate"):
            result["urgency"] = "routine"

        return result
    except Exception as e:
        logger.error(json.dumps({"stage": "timeline.error", "error": str(e)}))
        return {**FALLBACK, "error": str(e)}
