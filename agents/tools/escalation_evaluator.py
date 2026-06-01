"""
ClinIQ 2.0 — escalation_evaluator tool.

This is the autonomous clinical judgment layer of the watch loop.
Called by the watch_worker (not the planner) each time a patient
replies to a WhatsApp checkpoint.

Three-layer evaluation:
  1. Keyword screen — instant, catches obvious emergencies in any language
  2. Checkpoint criteria match — deterministic, uses the plan's own rules
  3. Groq clinical reasoning — only for ambiguous cases where rules are silent

Supabase is always updated after a decision: the checkpoint gets marked
'responded', and if escalation is warranted a new Escalation row is
created (which also flips the parent case to 'escalated').
"""

import json
import logging
import os
from uuid import UUID

from groq import AsyncGroq

from agents.tool_registry import REGISTRY, Tool
from db.models import Escalation
from db.timeline import write_timeline_event as _tl_write
from db.supabase_client import (
    complete_monitoring_plan,
    create_escalation,
    get_case,
    update_case_status,
    update_checkpoint,
)

logger = logging.getLogger("cliniq.tools.escalation_evaluator")

_GROQ_MODEL = "llama-3.3-70b-versatile"

# ===========================================================================
# Keyword signal lists — module-level constants, bilingual (EN + Hindi)
# ===========================================================================

EMERGENCY_KEYWORDS: list[str] = [
    "bleeding", "khoon", "blood",
    "unconscious", "behosh",
    "cannot breathe", "saans nahi",
    "chest pain", "seene mein dard",
    "fits", "seizure",
    "stroke", "paralysis", "laqwa",
    "cannot speak", "baat nahi",
    "faint", "gir gaya",
    "emergency", "hospital", "ambulance",
    "dying", "mar raha",
]

DETERIORATION_KEYWORDS: list[str] = [
    "worse", "zyada", "badh gaya", "increasing", "बढ़ रहा",
    "severe", "bahut zyada", "unbearable", "saha nahi",
    "not eating", "kuch nahi kha", "vomiting", "ulti",
    "cannot drink", "pi nahi",
    "very weak", "bahut kamzor",
    "high fever", "tez bukhar",
    "102", "103", "104", "105",
]

IMPROVEMENT_KEYWORDS: list[str] = [
    "better", "theek", "improving", "sudhar", "normal",
    "fine", "okay", "recovered", "theek ho gaya",
    "fever gone", "bukhar nahi",
    "eating well", "kha raha",
    "feeling good", "accha lag raha",
    "no pain", "dard nahi",
    "resolved", "cured", "bilkul theek",
]

CONCERN_KEYWORDS: list[str] = [
    "same", "waisa hi", "no change", "koi fark nahi",
    "still", "abhi bhi", "not improving", "sudhar nahi",
    "little better", "thoda", "slight", "mild",
]

# ===========================================================================
# Groq system prompt — PLACEHOLDER_ markers filled with .replace()
# ===========================================================================

_ESCALATION_PROMPT = """You are a clinical escalation evaluator for ClinIQ, \
an autonomous patient monitoring system in India.

A patient has replied to a monitoring checkpoint message.
Evaluate if this response requires escalation.

Case context:
Chief complaint: PLACEHOLDER_CHIEF_COMPLAINT
Diagnosis: PLACEHOLDER_TOP_DIAGNOSIS
Current risk tier: PLACEHOLDER_RISK_TIER
Day of monitoring: Day PLACEHOLDER_DAY_OFFSET

Checkpoint escalation criteria:
Escalate if: PLACEHOLDER_ESCALATE_IF
Watch if: PLACEHOLDER_WATCH_IF
Resolve if: PLACEHOLDER_RESOLVE_IF

Patient's response: "PLACEHOLDER_PATIENT_RESPONSE"

Keyword signals detected:
Emergency signals: PLACEHOLDER_EMERGENCY_SIGNALS
Deterioration signals: PLACEHOLDER_DETERIORATION_SIGNALS
Improvement signals: PLACEHOLDER_IMPROVEMENT_SIGNALS

Evaluate and return ONLY valid JSON, no markdown:
{
  "clinical_assessment": "one sentence assessment",
  "should_escalate": true or false,
  "severity": "watch|alert|emergency",
  "confidence": 0.0 to 1.0,
  "reason": "specific clinical reason for decision",
  "evidence": ["specific phrases from patient response"],
  "recommended_action": "what should happen next",
  "risk_change": "improved|stable|deteriorating|critical",
  "resolve_case": true or false
}

Rules for your response:
- If ANY emergency signal is present: should_escalate=true, severity=emergency
- If patient clearly improving with no concern signals: should_escalate=false, resolve_case based on day_offset
- If ambiguous: should_escalate=false, severity=watch, recommend follow-up question
- Never resolve a TB or malaria case before day 30
- Never resolve dengue before day 7"""


def _render_groq_prompt(
    case_history: dict,
    checkpoint: dict,
    patient_response: str,
    keyword_result: dict,
) -> str:
    diagnoses = case_history.get("diagnosis_hypotheses", [])
    top_diagnosis = diagnoses[0].get("diagnosis", "unknown") if diagnoses else "unknown"

    return (
        _ESCALATION_PROMPT
        .replace("PLACEHOLDER_CHIEF_COMPLAINT", str(case_history.get("chief_complaint", "not specified")))
        .replace("PLACEHOLDER_TOP_DIAGNOSIS", str(top_diagnosis))
        .replace("PLACEHOLDER_RISK_TIER", str(case_history.get("risk_tier", "low")))
        .replace("PLACEHOLDER_DAY_OFFSET", str(checkpoint.get("day_offset", "?")))
        .replace("PLACEHOLDER_ESCALATE_IF", json.dumps(checkpoint.get("escalate_if", [])))
        .replace("PLACEHOLDER_WATCH_IF", json.dumps(checkpoint.get("watch_if", [])))
        .replace("PLACEHOLDER_RESOLVE_IF", json.dumps(checkpoint.get("resolve_if", [])))
        .replace("PLACEHOLDER_PATIENT_RESPONSE", patient_response.replace('"', "'"))
        .replace("PLACEHOLDER_EMERGENCY_SIGNALS", json.dumps(keyword_result.get("emergency_signals", [])))
        .replace("PLACEHOLDER_DETERIORATION_SIGNALS", json.dumps(keyword_result.get("deterioration_signals", [])))
        .replace("PLACEHOLDER_IMPROVEMENT_SIGNALS", json.dumps(keyword_result.get("improvement_signals", [])))
    )


# ===========================================================================
# Groq client — lazily initialised
# ===========================================================================

_groq_client: AsyncGroq | None = None


def _get_groq() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY environment variable is not set")
        _groq_client = AsyncGroq(api_key=api_key)
    return _groq_client


# ===========================================================================
# Step 1 — keyword screen
# ===========================================================================


def keyword_screen(response_text: str) -> dict:
    """Fast bilingual pre-screen — always runs, no exceptions."""
    lower = response_text.lower()

    emergency_hits = [kw for kw in EMERGENCY_KEYWORDS if kw in lower]
    deterioration_hits = [kw for kw in DETERIORATION_KEYWORDS if kw in lower]
    improvement_hits = [kw for kw in IMPROVEMENT_KEYWORDS if kw in lower]
    concern_hits = [kw for kw in CONCERN_KEYWORDS if kw in lower]

    return {
        "emergency_signals":   emergency_hits,
        "deterioration_signals": deterioration_hits,
        "improvement_signals": improvement_hits,
        "concern_signals":     concern_hits,
        "has_emergency":       len(emergency_hits) > 0,
        "has_deterioration":   len(deterioration_hits) > 0,
        "has_improvement":     len(improvement_hits) > 0,
    }


# ===========================================================================
# Step 2 — checkpoint criteria matching
# ===========================================================================


def match_criteria(response_text: str, criteria_list: list[str]) -> list[str]:
    """
    Return the criteria from criteria_list whose key words appear in the
    patient response.  Short words (≤3 chars) are excluded to reduce noise.
    """
    lower = response_text.lower()
    matched: list[str] = []
    for criterion in criteria_list:
        key_words = [w for w in criterion.lower().split() if len(w) > 3]
        if any(word in lower for word in key_words):
            matched.append(criterion)
    return matched


def screen_criteria(response_text: str, checkpoint: dict) -> dict:
    """Run match_criteria against all three checkpoint criterion lists."""
    return {
        "escalate_matches": match_criteria(
            response_text, checkpoint.get("escalate_if", [])
        ),
        "watch_matches": match_criteria(
            response_text, checkpoint.get("watch_if", [])
        ),
        "resolve_matches": match_criteria(
            response_text, checkpoint.get("resolve_if", [])
        ),
    }


# ===========================================================================
# Step 3 — Groq clinical evaluation
# ===========================================================================


async def _call_groq(prompt: str) -> dict | None:
    """Call Groq and return parsed JSON, or None on any failure."""
    try:
        response = await _get_groq().chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Evaluate the patient response now."},
            ],
            temperature=0.1,
            max_tokens=512,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception:
        logger.exception("_call_groq: Groq call or parse failed")
        return None


async def groq_evaluate(
    case_history: dict,
    checkpoint: dict,
    patient_response: str,
    keyword_result: dict,
) -> dict | None:
    prompt = _render_groq_prompt(
        case_history, checkpoint, patient_response, keyword_result
    )
    result = await _call_groq(prompt)
    if result:
        # Normalise confidence to [0, 1]
        if "confidence" in result:
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
    return result


# ===========================================================================
# Step 4 — decision logic
# ===========================================================================

_RULE_BASED_DEFAULTS: dict = {
    "evidence": [],
    "recommended_action": "Continue monitoring and send next scheduled checkpoint.",
    "resolve_case": False,
    "clinical_assessment": "Decision made by rule engine.",
    "confidence": 1.0,
}


def make_decision(
    keyword_result: dict,
    criteria_matched: dict,
    groq_result: dict | None,
    checkpoint: dict,
    case_history: dict,
) -> dict:
    """
    Apply escalation rules in priority order.  Returns a normalised decision
    dict with all fields needed for the Supabase update and final response.
    """
    # RULE 1 — emergency override (highest priority)
    if keyword_result["has_emergency"]:
        return {
            **_RULE_BASED_DEFAULTS,
            "should_escalate": True,
            "severity": "emergency",
            "reason": "Emergency keywords detected in patient response",
            "risk_change": "critical",
            "evidence": keyword_result["emergency_signals"],
            "recommended_action": "Notify doctor immediately and call emergency services.",
            "clinical_assessment": "Emergency signals present — immediate intervention required.",
            "resolve_case": False,
        }

    # RULE 2 — checkpoint criteria-based escalation
    escalate_matches = criteria_matched.get("escalate_matches", [])
    if escalate_matches:
        return {
            **_RULE_BASED_DEFAULTS,
            "should_escalate": True,
            "severity": "alert",
            "reason": f"Escalation criteria met: {escalate_matches}",
            "risk_change": "deteriorating",
            "evidence": escalate_matches,
            "recommended_action": "Alert doctor and review case urgently.",
            "clinical_assessment": "Patient response matches checkpoint escalation criteria.",
            "confidence": 0.85,
            "resolve_case": False,
        }

    # RULE 3 — Groq clinical decision (ambiguous cases)
    if groq_result:
        return {
            "should_escalate": bool(groq_result.get("should_escalate", False)),
            "severity": groq_result.get("severity", "watch"),
            "reason": groq_result.get("reason", ""),
            "risk_change": groq_result.get("risk_change", "stable"),
            "evidence": groq_result.get("evidence", []),
            "recommended_action": groq_result.get("recommended_action", "Continue monitoring."),
            "resolve_case": bool(groq_result.get("resolve_case", False)),
            "clinical_assessment": groq_result.get("clinical_assessment", ""),
            "confidence": groq_result.get("confidence", 0.7),
        }

    # RULE 4 — clear improvement, no deterioration
    if keyword_result["has_improvement"] and not keyword_result["has_deterioration"]:
        return {
            **_RULE_BASED_DEFAULTS,
            "should_escalate": False,
            "severity": "watch",
            "reason": "Patient showing improvement",
            "risk_change": "improved",
            "evidence": keyword_result["improvement_signals"],
            "recommended_action": "Continue monitoring as scheduled.",
            "clinical_assessment": "Improvement signals detected — no immediate action needed.",
            "resolve_case": False,
        }

    # RULE 5 — default safe watch
    return {
        **_RULE_BASED_DEFAULTS,
        "should_escalate": False,
        "severity": "watch",
        "reason": "No clear escalation signals detected",
        "risk_change": "stable",
        "clinical_assessment": "Response does not indicate urgent concern.",
        "recommended_action": "Continue monitoring per scheduled checkpoints.",
        "resolve_case": False,
    }


# ===========================================================================
# Step 5 — Supabase updates
# ===========================================================================


async def _update_checkpoint_responded(
    plan_id: str | None,
    checkpoint: dict,
    patient_response: str,
    decision: dict,
) -> None:
    if not plan_id:
        logger.warning("_update_checkpoint_responded: no plan_id — skipping")
        return
    try:
        await update_checkpoint(
            plan_id=UUID(plan_id),
            day_offset=int(checkpoint.get("day_offset", 0)),
            status="responded",
            patient_response=patient_response,
            agent_evaluation={
                "risk_change":   decision.get("risk_change"),
                "action_taken":  decision.get("recommended_action"),
                "summary":       decision.get("clinical_assessment"),
            },
        )
    except Exception:
        logger.exception("_update_checkpoint_responded: update_checkpoint failed")


async def _create_escalation(
    case_id: str,
    patient_id: str,
    decision: dict,
    keyword_result: dict,
    criteria_matched: dict,
    groq_result: dict | None,
    checkpoint: dict,
    patient_response: str,
) -> str | None:
    try:
        escalation = Escalation(
            case_id=UUID(case_id),
            patient_id=UUID(patient_id),
            severity=decision.get("severity", "alert"),
            trigger_reason=decision.get("reason", ""),
            trigger_evidence={
                "patient_response": patient_response,
                "keyword_signals":  keyword_result,
                "criteria_matched": criteria_matched,
                "groq_assessment":  groq_result,
            },
            checkpoint_context=checkpoint,
        )
        saved = await create_escalation(escalation)
        return str(saved.escalation_id) if saved.escalation_id else None
    except Exception:
        logger.exception("_create_escalation: create_escalation failed")
        return None


async def _resolve_case_if_needed(
    decision: dict,
    case_id: str,
    plan_id: str | None,
) -> None:
    if not decision.get("resolve_case"):
        return
    try:
        await update_case_status(UUID(case_id), "resolved")
        logger.info("Case %s marked resolved", case_id)
    except Exception:
        logger.exception("_resolve_case_if_needed: update_case_status failed")

    if plan_id:
        try:
            await complete_monitoring_plan(UUID(plan_id))
            logger.info("Monitoring plan %s completed", plan_id)
        except Exception:
            logger.exception("_resolve_case_if_needed: complete_monitoring_plan failed")


# ===========================================================================
# Main tool function
# ===========================================================================


async def evaluate_escalation(inputs: dict) -> dict:
    """
    Evaluate a patient's WhatsApp reply and decide on escalation.

    Three-layer evaluation (keyword → criteria → Groq) with deterministic
    rule priority.  All Supabase updates run after the decision and never
    crash the evaluation.
    """
    case_id: str = inputs.get("case_id", "")
    patient_response: str = inputs.get("patient_response", "")
    checkpoint: dict = inputs.get("checkpoint", {})
    case_history: dict = inputs.get("case_history", {})
    plan_id: str | None = inputs.get("plan_id")
    patient_id: str | None = inputs.get("patient_id")

    logger.info(
        "evaluate_escalation | case=%s | day_offset=%s | response_len=%d",
        case_id,
        checkpoint.get("day_offset", "?"),
        len(patient_response),
    )

    if not patient_response.strip():
        logger.warning("evaluate_escalation: empty patient_response for case %s", case_id)

    # Resolve patient_id (needed for Escalation row)
    if not patient_id:
        try:
            case_obj = await get_case(UUID(case_id))
            if case_obj:
                patient_id = str(case_obj.patient_id)
        except Exception:
            logger.exception("evaluate_escalation: could not resolve patient_id for case %s", case_id)

    # --- Step 1: keyword screen (always runs) ---
    keyword_result = keyword_screen(patient_response)
    logger.debug(
        "keyword_screen | emergency=%s | deterioration=%s | improvement=%s",
        keyword_result["has_emergency"],
        keyword_result["has_deterioration"],
        keyword_result["has_improvement"],
    )

    # --- Step 2: checkpoint criteria matching ---
    criteria_matched = screen_criteria(patient_response, checkpoint)

    # --- Step 3: Groq (only for ambiguous cases) ---
    skip_groq = keyword_result["has_emergency"] or (
        keyword_result["has_improvement"] and not keyword_result["has_deterioration"]
    )
    groq_result: dict | None = None
    evaluation_method = "rule_based"

    if not skip_groq:
        groq_result = await groq_evaluate(
            case_history, checkpoint, patient_response, keyword_result
        )
        if groq_result:
            evaluation_method = "groq_assisted"
            logger.info("Groq evaluation completed | confidence=%.2f", groq_result.get("confidence", 0))

    # --- Step 4: decision ---
    decision = make_decision(
        keyword_result, criteria_matched, groq_result, checkpoint, case_history
    )

    logger.info(
        "evaluate_escalation DECISION | method=%s | escalate=%s | severity=%s | risk_change=%s",
        evaluation_method,
        decision["should_escalate"],
        decision["severity"],
        decision["risk_change"],
    )

    # --- Step 5: Supabase updates ---
    await _update_checkpoint_responded(
        plan_id, checkpoint, patient_response, decision
    )

    escalation_id: str | None = None
    if decision["should_escalate"] and patient_id:
        escalation_id = await _create_escalation(
            case_id, patient_id, decision,
            keyword_result, criteria_matched, groq_result,
            checkpoint, patient_response,
        )
        if escalation_id:
            logger.info("Escalation created | id=%s | severity=%s", escalation_id, decision["severity"])

            # Derive trigger_source from evaluation path (keyword > criteria > groq).
            if keyword_result.get("has_emergency"):
                trigger_source = "keyword"
            elif criteria_matched.get("escalate_matches"):
                trigger_source = "checkpoint"
            elif evaluation_method == "groq_assisted":
                trigger_source = "groq"
            else:
                trigger_source = "checkpoint"

            # Write timeline event after escalation row is written.
            await _tl_write(
                case_id    = case_id,
                event_type = "escalation_triggered",
                payload    = {
                    "trigger_source":  trigger_source,
                    "trigger_reason":  decision.get("reason", ""),
                    "severity":        decision.get("severity", "alert"),
                    "escalation_id":   escalation_id,
                },
                agent_name = "EscalationEvaluator",
            )

    await _resolve_case_if_needed(decision, case_id, plan_id)

    # --- Step 6: return ---
    return {
        "should_escalate":             decision["should_escalate"],
        "severity":                    decision["severity"],
        "reason":                      decision["reason"],
        "evidence":                    decision.get("evidence", []),
        "risk_change":                 decision.get("risk_change", "stable"),
        "recommended_action":          decision.get("recommended_action", ""),
        "resolve_case":                decision.get("resolve_case", False),
        "escalation_id":               escalation_id,
        "clinical_assessment":         decision.get("clinical_assessment", ""),
        "evaluation_method":           evaluation_method,
        "keyword_signals":             keyword_result,
        "checkpoint_criteria_matched": criteria_matched,
    }


# ===========================================================================
# Re-register with real implementation
# ===========================================================================

REGISTRY.register(
    Tool(
        name="escalation_evaluator",
        description="Evaluate patient WhatsApp reply against checkpoint criteria and decide if escalation needed",
        input_schema={
            "type": "object",
            "properties": {
                "case_id":          {"type": "string"},
                "patient_response": {"type": "string"},
                "checkpoint":       {"type": "object"},
                "case_history":     {"type": "object"},
                "plan_id":          {"type": "string"},
                "patient_id":       {"type": "string"},
            },
            "required": ["case_id", "patient_response", "checkpoint"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "should_escalate":             {"type": "boolean"},
                "severity":                    {"type": "string"},
                "reason":                      {"type": "string"},
                "risk_change":                 {"type": "string"},
                "escalation_id":               {"type": ["string", "null"]},
                "evaluation_method":           {"type": "string"},
                "keyword_signals":             {"type": "object"},
                "checkpoint_criteria_matched": {"type": "object"},
            },
        },
        agent="watch_agent",
        async_fn=evaluate_escalation,
    )
)

logger.debug("escalation_evaluator: real implementation registered")
