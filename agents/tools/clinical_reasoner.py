"""
ClinIQ 2.0 — clinical_reasoner tool.

Replaces the registry stub.  Takes structured symptoms plus patient
demographics and produces differential diagnoses, risk stratification,
and recommended tests/medications — all tuned for Indian clinical context.
"""

import json
import logging
import os

from agents.tool_registry import REGISTRY, Tool
from backend.llm.router import llm_chat
from backend.llm.parsing import parse_llm_json

logger = logging.getLogger("cliniq.tools.clinical_reasoner")

_RISK_ORDER = ["low", "moderate", "high", "critical"]

# ---------------------------------------------------------------------------
# System prompt — embedded exactly as specified.
# Placeholders use PLACEHOLDER_ prefix so .replace() doesn't clash with
# the literal JSON braces in the return-schema section of the prompt.
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a senior clinical reasoning engine for an Indian medical AI. Generate differential diagnoses for Indian patients.

CRITICAL INDIA-SPECIFIC RULES:
- Always consider TB in any patient with cough > 2 weeks, weight loss, night sweats, regardless of other findings
- Consider dengue in any fever case during June-November
- Consider typhoid in fever with abdominal symptoms in patients under 40
- Consider malaria in fever with chills, especially in states: Odisha, Jharkhand, Chhattisgarh, MP, Maharashtra tribal areas, Northeast
- Consider chikungunya/dengue co-infection during outbreaks
- Iron deficiency anemia is extremely common, especially in women and children
- Vitamin B12 deficiency common in vegetarians
- Consider diabetes complications in patients over 35
- Rheumatic heart disease still prevalent in young adults

Patient: PLACEHOLDER_AGEyr PLACEHOLDER_SEX, Location: PLACEHOLDER_LOCATION
Symptoms: PLACEHOLDER_SYMPTOMS_JSON
Known conditions: PLACEHOLDER_KNOWN_CONDITIONS
Lab findings: PLACEHOLDER_LAB_FINDINGS

Return ONLY valid JSON, no markdown:
{
  "differentials": [
    {
      "diagnosis": "diagnosis name",
      "icd_code": "ICD-11 code if known",
      "confidence": 0.0 to 1.0,
      "evidence": ["symptom or finding supporting this"],
      "against": ["findings that argue against this"],
      "india_prevalence": "high|moderate|low",
      "urgency": "routine|urgent|emergency"
    }
  ],
  "risk_tier": "low|moderate|high|critical",
  "risk_flags": ["specific concerning findings"],
  "recommended_tests": [
    {
      "test": "test name",
      "reason": "why this test",
      "priority": "immediate|within_48h|within_week|routine"
    }
  ],
  "recommended_medications": [
    {
      "drug": "generic name",
      "indication": "why",
      "note": "any caution"
    }
  ],
  "red_flag_actions": ["immediate actions if any red flags"],
  "reasoning_summary": "2-3 sentence clinical summary"
}

Limit to top 5 differentials, ordered by confidence descending."""

_REQUIRED_FIELDS = {
    "differentials",
    "risk_tier",
    "risk_flags",
    "recommended_tests",
    "recommended_medications",
    "red_flag_actions",
    "reasoning_summary",
}

# ---------------------------------------------------------------------------
# Fallback response
# ---------------------------------------------------------------------------


def _fallback(inputs: dict, error: str) -> dict:
    return {
        "differentials": [],
        "risk_tier": "low",
        "risk_flags": [],
        "recommended_tests": [],
        "recommended_medications": [],
        "red_flag_actions": [],
        "reasoning_summary": "Clinical reasoning unavailable — manual review required.",
        "error": error,
    }


# ---------------------------------------------------------------------------
# Risk tier override
# ---------------------------------------------------------------------------


def _apply_risk_rules(result: dict) -> dict:
    """
    Enforce deterministic risk escalation rules on top of whatever Groq returned.

    Rules (highest wins):
      - Any differential with urgency=emergency  → critical
      - Non-empty red_flags                      → at least high
      - Groq's own risk_tier is the floor
    """
    llm_tier: str = result.get("risk_tier", "low")
    computed_tier = llm_tier

    if result.get("red_flags"):
        computed_tier = _max_tier(computed_tier, "high")

    for diff in result.get("differentials", []):
        if diff.get("urgency") == "emergency":
            computed_tier = "critical"
            break

    if computed_tier != llm_tier:
        logger.info(
            "risk_tier escalated by rules: %s → %s", llm_tier, computed_tier
        )

    result["risk_tier"] = computed_tier
    return result


def _max_tier(a: str, b: str) -> str:
    """Return the higher of two risk tier strings."""
    return max(a, b, key=lambda t: _RISK_ORDER.index(t) if t in _RISK_ORDER else -1)


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------


def _render_prompt(inputs: dict) -> str:
    symptoms = inputs.get("symptoms", [])
    known = inputs.get("known_conditions", [])
    lab = inputs.get("lab_findings", {})

    return (
        _SYSTEM_PROMPT
        .replace("PLACEHOLDER_AGE", str(inputs.get("patient_age", "unknown")))
        .replace("PLACEHOLDER_SEX", str(inputs.get("patient_sex", "unknown")))
        .replace("PLACEHOLDER_LOCATION", str(inputs.get("location", "India")))
        .replace("PLACEHOLDER_SYMPTOMS_JSON", json.dumps(symptoms, ensure_ascii=False))
        .replace(
            "PLACEHOLDER_KNOWN_CONDITIONS",
            ", ".join(known) if known else "none reported",
        )
        .replace(
            "PLACEHOLDER_LAB_FINDINGS",
            json.dumps(lab, ensure_ascii=False) if lab else "none available",
        )
    )


# ---------------------------------------------------------------------------
# Groq call + parse
# ---------------------------------------------------------------------------


async def _call_groq(system_prompt: str, inputs: dict) -> str:
    user_msg = (
        f"Please analyse this patient and return the JSON differential diagnosis."
        f" Symptoms count: {len(inputs.get('symptoms', []))}."
    )
    return await llm_chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
        max_tokens=2048,
    )


def _parse_and_validate(raw: str) -> dict:
    try:
        data: dict = parse_llm_json(raw)
    except Exception as e:
        logger.error("JSON parse failed: %s", e)
        logger.error("Raw text was: %s", raw[:500])
        raise

    missing = _REQUIRED_FIELDS - data.keys()
    if missing:
        raise ValueError(f"Response missing required fields: {missing}")

    # Coerce all differential confidence values to [0, 1]
    for diff in data.get("differentials", []):
        if "confidence" in diff:
            diff["confidence"] = max(0.0, min(1.0, float(diff["confidence"])))

    return data


# ---------------------------------------------------------------------------
# Main tool function
# ---------------------------------------------------------------------------


async def reason_clinically(inputs: dict) -> dict:
    """
    Generate differential diagnoses and risk stratification from symptoms.

    Combines Groq's clinical reasoning with deterministic India-specific
    risk escalation rules applied after the LLM response is parsed.
    """
    symptoms = inputs.get("symptoms", [])
    print(f"DIAGNOSES IN: {symptoms}")
    logger.info(
        "reason_clinically | age=%s | sex=%s | symptoms=%d | location=%s",
        inputs.get("patient_age"),
        inputs.get("patient_sex"),
        len(symptoms),
        inputs.get("location", "unknown"),
    )

    if not symptoms:
        logger.warning("reason_clinically called with no symptoms — returning low-risk default")
        return _fallback(inputs, "no_symptoms_provided")

    system_prompt = _render_prompt(inputs)

    try:
        raw = await _call_groq(system_prompt, inputs)
    except Exception:
        logger.exception("reason_clinically: Groq call failed")
        return _fallback(inputs, "reasoning_failed")

    try:
        result = _parse_and_validate(raw)
    except Exception:
        logger.exception(
            "reason_clinically: parse/validation failed | raw=%s", raw[:200]
        )
        return _fallback(inputs, "reasoning_failed")

    result = _apply_risk_rules(result)
    diagnoses = result.get("differentials", [])
    print(f"DIAGNOSES OUT: {diagnoses}")

    logger.info(
        "reason_clinically OK | differentials=%d | risk=%s | flags=%d",
        len(result.get("differentials", [])),
        result.get("risk_tier"),
        len(result.get("risk_flags", [])),
    )
    return result


# ---------------------------------------------------------------------------
# Re-register with real implementation
# ---------------------------------------------------------------------------

REGISTRY.register(
    Tool(
        name="clinical_reasoner",
        description="Generate differential diagnoses from symptoms and patient context",
        input_schema={
            "type": "object",
            "properties": {
                "symptoms":          {"type": "array"},
                "patient_age":       {"type": "integer"},
                "patient_sex":       {"type": "string"},
                "known_conditions":  {"type": "array", "items": {"type": "string"}},
                "lab_findings":      {"type": "object"},
                "location":          {"type": "string"},
            },
            "required": ["symptoms"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "differentials":         {"type": "array"},
                "risk_tier":             {"type": "string"},
                "risk_flags":            {"type": "array"},
                "recommended_tests":     {"type": "array"},
                "recommended_medications": {"type": "array"},
                "red_flag_actions":      {"type": "array"},
                "reasoning_summary":     {"type": "string"},
            },
        },
        agent="clinical_agent",
        async_fn=reason_clinically,
    )
)

logger.debug("clinical_reasoner: real implementation registered")
