"""
ClinIQ 2.0 — Lab report DeepDive package.

Entry point: run_deepdive(inputs) routes to the correct interpreter
based on report_type.  CBC and LFT get full rule-based + Groq specialist
pipelines; all other report types fall through to generic_interpret.

Registered in REGISTRY as "lab_interpreter" — replaces the stub.
"""

import json
import logging
import os

from groq import AsyncGroq

from agents.tool_registry import REGISTRY, Tool
from agents.tools.deepdive.cbc_interpreter import interpret_cbc
from agents.tools.deepdive.lft_interpreter import interpret_lft
from agents.tools.deepdive.rft_interpreter import interpret_rft
from db.timeline import write_timeline_event as _tl_write

logger = logging.getLogger("cliniq.tools.deepdive")

_GROQ_MODEL = "llama-3.3-70b-versatile"

# ---------------------------------------------------------------------------
# Lazy Groq client for generic interpreter
# ---------------------------------------------------------------------------

_groq_client: AsyncGroq | None = None


def _get_groq() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY environment variable is not set")
        _groq_client = AsyncGroq(api_key=api_key)
    return _groq_client


# ---------------------------------------------------------------------------
# Generic interpreter — fallback for LFT, RFT, Xray, prescription, other
# ---------------------------------------------------------------------------

_GENERIC_PROMPT = """You are a lab report interpreter for Indian patients.
Analyze this lab report and return key findings, abnormal values, risk level, \
and recommended actions.

Report text: PLACEHOLDER_RAW_TEXT
Patient: PLACEHOLDER_AGEyr PLACEHOLDER_SEX
Known conditions: PLACEHOLDER_KNOWN_CONDITIONS

Return ONLY valid JSON, no markdown:
{
  "findings": ["key finding 1", "key finding 2"],
  "abnormal_values": [
    {"marker": "name", "value": "value", "interpretation": "what it means"}
  ],
  "risk_level": "low|moderate|high|critical",
  "risk_reason": "why",
  "follow_up_tests": [
    {"test": "name", "reason": "why", "priority": "immediate|48h|week"}
  ],
  "immediate_actions": [],
  "india_context": "India-specific note if relevant",
  "patient_explanation": "simple language explanation",
  "monitoring_needed": true or false
}"""


async def generic_interpret(inputs: dict) -> dict:
    """
    Groq-based interpretation for non-CBC report types.
    Returns a normalised dict matching the lab_interpreter output schema.
    """
    raw_text: str = inputs.get("raw_text", "")
    age: int = int(inputs.get("patient_age", 30))
    sex: str = str(inputs.get("patient_sex", "unknown"))
    known_conditions: list[str] = inputs.get("known_conditions", [])
    report_type: str = inputs.get("report_type", "other")

    logger.info(
        "generic_interpret | report_type=%s | age=%d | text_len=%d",
        report_type, age, len(raw_text),
    )

    prompt = (
        _GENERIC_PROMPT
        .replace("PLACEHOLDER_RAW_TEXT", raw_text[:3000])  # guard against huge PDFs
        .replace("PLACEHOLDER_AGE", str(age))
        .replace("PLACEHOLDER_SEX", sex)
        .replace("PLACEHOLDER_KNOWN_CONDITIONS", ", ".join(known_conditions) or "none")
    )

    try:
        response = await _get_groq().chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Interpret this {report_type} report now."},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        data = json.loads(raw)
        logger.info("generic_interpret OK | risk=%s", data.get("risk_level", "?"))
        return {
            "report_type":         report_type,
            "parsed_values":       {},
            "values_count":        0,
            "abnormal_flags":      data.get("abnormal_values", []),
            "abnormal_count":      len(data.get("abnormal_values", [])),
            "patterns_detected":   [],
            "primary_pattern":     None,
            "risk_level":          data.get("risk_level", "low"),
            "risk_reason":         data.get("risk_reason", ""),
            "immediate_actions":   data.get("immediate_actions", []),
            "follow_up_tests":     data.get("follow_up_tests", []),
            "clinical_summary":    "\n".join(data.get("findings", [])),
            "primary_finding":     data.get("findings", [""])[0] if data.get("findings") else "",
            "india_context":       data.get("india_context", ""),
            "patient_explanation": data.get("patient_explanation", ""),
            "monitoring_needed":   bool(data.get("monitoring_needed", False)),
        }

    except Exception:
        logger.exception("generic_interpret: Groq failed for report_type=%s", report_type)
        return {
            "report_type":         report_type,
            "parsed_values":       {},
            "values_count":        0,
            "abnormal_flags":      [],
            "abnormal_count":      0,
            "patterns_detected":   [],
            "primary_pattern":     None,
            "risk_level":          "low",
            "risk_reason":         "Interpretation unavailable",
            "immediate_actions":   [],
            "follow_up_tests":     [],
            "clinical_summary":    "Lab report received. Manual review required.",
            "primary_finding":     "",
            "india_context":       "",
            "patient_explanation": "Your lab report has been received. "
                                   "Please see your doctor for detailed explanation.",
            "monitoring_needed":   False,
            "error":               "groq_unavailable",
        }


# ---------------------------------------------------------------------------
# Router — dispatches to CBC specialist or generic fallback
# ---------------------------------------------------------------------------


_SPECIALIST: dict[str, str] = {
    "CBC": "Haematology",
    "LFT": "Hepatology",
    "RFT": "Nephrology",
}


async def run_deepdive(inputs: dict) -> dict:
    """
    Route to the correct interpreter based on report_type.

    report_type == "CBC"  → full rule-based CBC pipeline
    all others            → Groq generic interpreter
    """
    report_type: str = inputs.get("report_type", "other")
    case_id: str | None = inputs.get("case_id") or None
    logger.info("run_deepdive | report_type=%s", report_type)

    if report_type == "CBC":
        result = await interpret_cbc(inputs)
    elif report_type == "LFT":
        result = await interpret_lft(inputs)
    elif report_type == "RFT":
        result = await interpret_rft(inputs)
    else:
        result = await generic_interpret(inputs)

    # Write timeline event after interpreter completes successfully.
    # Uses case_id from inputs if present; silently skips when absent.
    await _tl_write(
        case_id    = case_id,
        event_type = "deepdive_complete",
        payload    = {
            "report_type":         result.get("report_type", report_type),
            "specialist":          _SPECIALIST.get(report_type, "Clinical"),
            "findings":            [result["primary_finding"]] if result.get("primary_finding") else
                                   result.get("clinical_summary", "")[:200].split(". ")[:3],
            "patterns":            result.get("patterns_detected", []),
            "risk_score":          result.get("risk_level", "unknown"),
            "critical_flags":      [f for f in result.get("abnormal_flags", [])
                                    if isinstance(f, dict) and f.get("severity") == "critical"],
            "escalation_required": result.get("risk_level") in ("high", "critical")
                                   or bool(result.get("monitoring_needed", False)),
        },
        agent_name = f"{report_type}Interpreter",
    )

    return result


# ---------------------------------------------------------------------------
# Re-register lab_interpreter with real implementation
# ---------------------------------------------------------------------------

REGISTRY.register(
    Tool(
        name="lab_interpreter",
        description="Run DeepDive analysis on uploaded lab report",
        input_schema={
            "type": "object",
            "properties": {
                "report_type":      {"type": "string"},
                "raw_text":         {"type": "string"},
                "patient_age":      {"type": "integer"},
                "patient_sex":      {"type": "string"},
                "known_conditions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["report_type", "raw_text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "report_type":       {"type": "string"},
                "parsed_values":     {"type": "object"},
                "abnormal_flags":    {"type": "array"},
                "patterns_detected": {"type": "array"},
                "risk_level":        {"type": "string"},
                "clinical_summary":  {"type": "string"},
                "follow_up_tests":   {"type": "array"},
                "patient_explanation": {"type": "string"},
                "monitoring_needed": {"type": "boolean"},
            },
        },
        agent="deepdive_agent",
        async_fn=run_deepdive,
    )
)

logger.debug("lab_interpreter: real implementation registered (CBC + generic)")
