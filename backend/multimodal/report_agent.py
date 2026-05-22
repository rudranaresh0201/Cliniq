import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import logging
from backend.llm.router import complete, parse_json

logger = logging.getLogger("cliniq")

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_LAB_PROMPT = """You are a medical lab report interpreter. A patient has uploaded their lab results.

Abnormal / flagged values:
{abnormal_values}

Patient context:
{patient_context}

For each abnormal value explain:
1. What the test measures
2. What the abnormal result means clinically
3. Possible causes
4. What the patient should do next

Return ONLY a valid JSON object:
{{
  "interpretation": "<2-4 sentence plain English overview>",
  "abnormal_explanations": [
    {{
      "test": "<test name>",
      "value": "<value with unit>",
      "flag": "<HIGH|LOW|CRITICAL_HIGH|CRITICAL_LOW>",
      "meaning": "<plain English meaning>",
      "possible_causes": ["<cause 1>", "<cause 2>"],
      "action": "<what to do>"
    }}
  ],
  "overall_urgency": "<routine|urgent|immediate>",
  "recommended_followup": "<specific doctor type or test to get next>"
}}"""

_IMAGING_PROMPT = """You are a senior Indian radiologist explaining a {report_type_label} report to a patient in plain English.

Report text:
{raw_text}

Patient context: {patient_context}

Explain:
1. What the report found (in plain English)
2. What it means for the patient
3. How serious it is (routine/concerning/urgent)
4. What questions to ask the doctor
5. What follow-up is typically needed

Be reassuring but honest. Use simple language. Avoid medical jargon or explain it immediately.

Return ONLY a valid JSON object:
{{
  "interpretation": "<2-3 sentence plain English overview>",
  "findings": ["<finding 1>", "<finding 2>"],
  "what_it_means": "<plain English explanation for patient>",
  "overall_urgency": "<routine|urgent|immediate>",
  "questions_to_ask": ["<question 1>", "<question 2>", "<question 3>"],
  "recommended_followup": "<specific next step>"
}}"""

_PRESCRIPTION_PROMPT = """You are an Indian clinical pharmacist explaining a prescription to a patient in plain English.

Prescription text:
{raw_text}

Patient context: {patient_context}

Explain:
1. Each medicine: what it is and what it does
2. How and when to take each medicine
3. Common side effects to watch for
4. Any important warnings or drug interactions
5. How long to continue each medicine

Be clear and practical. The patient needs to understand exactly what to do.

Return ONLY a valid JSON object:
{{
  "interpretation": "<2-3 sentence overview of the prescription>",
  "medicines": [
    {{
      "name": "<medicine name and dose>",
      "purpose": "<what this medicine is for>",
      "how_to_take": "<timing and instructions>",
      "side_effects": ["<side effect 1>"],
      "duration": "<how long to take it>"
    }}
  ],
  "important_warnings": ["<warning 1>", "<warning 2>"],
  "overall_urgency": "routine",
  "recommended_followup": "<when to see the doctor again>"
}}"""

_IMAGING_TYPE_LABELS: dict[str, str] = {
    "xray_report": "X-Ray",
    "mri_report":  "MRI",
    "ct_report":   "CT Scan",
    "ecg_report":  "ECG",
}

FALLBACK = {
    "interpretation": "Unable to interpret the report automatically. Please show these results to your doctor.",
    "abnormal_explanations": [],
    "findings": [],
    "what_it_means": "",
    "questions_to_ask": [],
    "medicines": [],
    "important_warnings": [],
    "overall_urgency": "routine",
    "recommended_followup": "Consult your primary care physician with these results.",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_abnormal(values: dict) -> str:
    abnormal = {k: v for k, v in values.items() if v.get("flag", "NORMAL") != "NORMAL"}
    if not abnormal:
        return "No abnormal values detected."
    lines = []
    for name, info in abnormal.items():
        lines.append(
            f"- {name.upper()}: {info['value']} {info['unit']} "
            f"(normal {info['normal_low']}–{info['normal_high']}) → {info['flag']}"
        )
    return "\n".join(lines)


def _format_patient_context(ctx: dict) -> str:
    if not ctx:
        return "Not provided"
    parts = []
    if ctx.get("age"):
        parts.append(f"Age: {ctx['age']}")
    if ctx.get("gender"):
        parts.append(f"Gender: {ctx['gender']}")
    if ctx.get("existing_conditions"):
        parts.append(f"Conditions: {', '.join(ctx['existing_conditions'])}")
    if ctx.get("medications"):
        parts.append(f"Medications: {', '.join(ctx['medications'])}")
    return " | ".join(parts) if parts else "Not provided"


# ---------------------------------------------------------------------------
# Main interpreter
# ---------------------------------------------------------------------------

async def interpret_report(parsed: dict, patient_context: dict | None = None) -> dict:
    """
    Interpret a parsed report using the LLM router.

    Args:
        parsed: Full output from report_parser.parse_report().
        patient_context: Optional dict with age, gender, medications, existing_conditions.

    Returns:
        Dict with interpretation and type-specific fields.
    """
    context_text = _format_patient_context(patient_context or {})
    report_type = parsed.get("report_type", "general_medical")

    if parsed.get("is_imaging_report"):
        label = _IMAGING_TYPE_LABELS.get(report_type, "Imaging")
        prompt = _IMAGING_PROMPT.format(
            report_type_label=label,
            raw_text=parsed.get("raw_text", "")[:2000],
            patient_context=context_text,
        )
    elif parsed.get("is_prescription"):
        prompt = _PRESCRIPTION_PROMPT.format(
            raw_text=parsed.get("raw_text", "")[:2000],
            patient_context=context_text,
        )
    else:
        prompt = _LAB_PROMPT.format(
            abnormal_values=_format_abnormal(parsed.get("values", {})),
            patient_context=context_text,
        )

    try:
        raw, provider = await complete(prompt, temperature=0.2, max_tokens=1200)
        logger.info(json.dumps({"stage": "report_agent.provider", "provider": provider}))
        result = parse_json(raw)

        result.setdefault("interpretation", FALLBACK["interpretation"])
        result.setdefault("overall_urgency", "routine")
        result.setdefault("recommended_followup", FALLBACK["recommended_followup"])

        if result.get("overall_urgency") not in ("routine", "urgent", "immediate"):
            result["overall_urgency"] = "routine"

        # Type-specific defaults
        if parsed.get("is_imaging_report"):
            result.setdefault("findings", [])
            result.setdefault("what_it_means", "")
            result.setdefault("questions_to_ask", [])
        elif parsed.get("is_prescription"):
            result.setdefault("medicines", [])
            result.setdefault("important_warnings", [])
        else:
            result.setdefault("abnormal_explanations", [])

        return result
    except Exception as e:
        logger.error(json.dumps({"stage": "report_agent.error", "error": str(e)}))
        return {**FALLBACK, "error": str(e)}
