"""
ClinIQ 2.0 — Intelligence read-only endpoints.

Five GET endpoints that surface aggregated patient intelligence to
the Console and Patient-OS front-ends.  All reads are safe:
  • 404 for unknown case_id / patient_id
  • Empty list [] (never null) for list fields
  • Safe numeric defaults instead of 500s when sub-queries fail

Registered in backend/main.py with prefix="/api".
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status

from db.supabase_client import get_client, get_patient

logger = logging.getLogger("cliniq.routers.intelligence")

router = APIRouter(tags=["Intelligence"])

# ---------------------------------------------------------------------------
# Table name constants  (duplicated from supabase_client to avoid coupling)
# ---------------------------------------------------------------------------

_TBL_TIMELINE   = "timeline_events"
_TBL_AGENT_ACT  = "agent_activity"
_TBL_MON_PLANS  = "monitoring_plans"
_TBL_ESCALATE   = "escalations"
_TBL_CASES      = "cases"
_TBL_PATIENTS   = "patients"

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _iso(value: Any) -> str:
    """Coerce a DB timestamp / datetime / None to a safe ISO-8601 string."""
    if value is None:
        return datetime.now(tz=timezone.utc).isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    # Supabase returns timestamps as strings; normalise "+00:00" suffix
    return str(value)


def _agent_from_title(title: str) -> str:
    """
    Extract agent name from the '{AgentName}: {action}' title format
    written by db/timeline.py.  Falls back to "System".
    """
    if title and ":" in title:
        return title.split(":", 1)[0].strip()
    return "System"


def _dt_parse(raw: Any) -> datetime | None:
    """Parse a raw DB timestamp to a timezone-aware datetime, or None."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


# Severity → composite sort weight  (higher = more urgent)
_SEV_SCORE: dict[str, int] = {
    "emergency": 100,
    "critical":  100,
    "alert":      50,
    "warning":    50,
    "watch":      25,
}

# Severity → display name for frontend
_SEV_DISPLAY: dict[str, str] = {
    "emergency": "critical",
    "critical":  "critical",
    "alert":     "warning",
    "warning":   "warning",
    "watch":     "warning",
}

# risk_level string → numeric health rank (higher = healthier)
_RISK_RANK: dict[str, int] = {
    "low":      4,
    "moderate": 3,
    "high":     2,
    "critical": 1,
    "unknown":  2,
}


async def _verify_case_exists(db, case_id: UUID) -> None:
    """Raise 404 if the case row cannot be found."""
    res = (
        await db.table(_TBL_CASES)
        .select("case_id")
        .eq("case_id", str(case_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )


# ---------------------------------------------------------------------------
# ENDPOINT 1: GET /cases/{case_id}/timeline
# ---------------------------------------------------------------------------

@router.get("/cases/{case_id}/timeline")
async def case_timeline(case_id: UUID) -> dict:
    """
    Return the last 50 timeline events for a case, newest first.

    Queries timeline_events ordered by event_date DESC.
    agent_name is extracted from the event title written by db/timeline.py.
    """
    db = await get_client()
    await _verify_case_exists(db, case_id)

    events: list[dict] = []
    try:
        res = (
            await db.table(_TBL_TIMELINE)
            .select("*")
            .eq("case_id", str(case_id))
            .order("event_date", desc=True)
            .limit(50)
            .execute()
        )
        for row in res.data:
            events.append({
                "id":         str(row.get("event_id") or row.get("id") or ""),
                "event_type": row.get("event_type", ""),
                "payload":    row.get("content") or {},
                "created_at": _iso(row.get("created_at") or row.get("event_date")),
                "agent_name": _agent_from_title(str(row.get("title") or "")),
            })
    except Exception:
        logger.exception("case_timeline: query failed | case=%s", case_id)

    return {"events": events}


# ---------------------------------------------------------------------------
# ENDPOINT 2: GET /cases/{case_id}/monitoring-status
# ---------------------------------------------------------------------------

@router.get("/cases/{case_id}/monitoring-status")
async def monitoring_status(case_id: UUID) -> dict:
    """
    Return the active monitoring protocol progress for a case.

    Reads the active monitoring_plan and computes adherence from
    checkpoint statuses stored in the JSONB checkpoints array.
    """
    db = await get_client()
    await _verify_case_exists(db, case_id)

    _default = {
        "active":                False,
        "protocol_name":         "",
        "disease":               "",
        "total_checkpoints":     0,
        "completed_checkpoints": 0,
        "next_checkpoint_at":    None,
        "adherence_percent":     0,
        "day_current":           0,
        "day_total":             0,
    }

    try:
        plans_res = (
            await db.table(_TBL_MON_PLANS)
            .select("*")
            .eq("case_id", str(case_id))
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("monitoring_status: query failed | case=%s", case_id)
        return _default

    if not plans_res.data:
        return _default

    plan = plans_res.data[0]
    checkpoints: list[dict] = plan.get("checkpoints") or []
    if not isinstance(checkpoints, list):
        checkpoints = []

    total      = len(checkpoints)
    completed  = sum(1 for cp in checkpoints
                     if isinstance(cp, dict) and cp.get("status") == "responded")
    adherence  = int((completed / total) * 100) if total > 0 else 0

    # Next checkpoint = earliest pending/sent by scheduled_date
    pending = [
        cp for cp in checkpoints
        if isinstance(cp, dict) and cp.get("status") in ("pending", "sent")
    ]
    pending_sorted = sorted(pending, key=lambda c: str(c.get("scheduled_date", "")))
    next_at = pending_sorted[0].get("scheduled_date") if pending_sorted else None

    # day_total = highest day_offset in plan
    day_offsets = [cp["day_offset"] for cp in checkpoints
                   if isinstance(cp, dict) and isinstance(cp.get("day_offset"), int)]
    day_total = max(day_offsets) if day_offsets else 0

    # day_current = elapsed days since plan created_at
    plan_created = _dt_parse(plan.get("created_at"))
    day_current = (
        (datetime.now(tz=timezone.utc) - plan_created).days
        if plan_created else 0
    )

    diagnosis_ctx = str(plan.get("diagnosis_context") or "")

    return {
        "active":                True,
        "protocol_name":         diagnosis_ctx,
        "disease":               diagnosis_ctx,
        "total_checkpoints":     total,
        "completed_checkpoints": completed,
        "next_checkpoint_at":    str(next_at) if next_at else None,
        "adherence_percent":     adherence,
        "day_current":           min(day_current, day_total),
        "day_total":             day_total,
    }


# ---------------------------------------------------------------------------
# ENDPOINT 3: GET /patients/{patient_id}/recovery-score
# ---------------------------------------------------------------------------

@router.get("/patients/{patient_id}/recovery-score")
async def recovery_score(patient_id: UUID) -> dict:
    """
    Compute a 0-100 recovery score from adherence, lab trajectory, and
    time since last escalation.  Safe defaults are returned for every
    sub-query that fails.
    """
    db = await get_client()

    patient = await get_patient(patient_id)
    if patient is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found",
        )

    # -----------------------------------------------------------------
    # Step 0 — find the most recent active case for this patient
    # -----------------------------------------------------------------
    try:
        cases_res = (
            await db.table(_TBL_CASES)
            .select("case_id,created_at")
            .eq("patient_id", str(patient_id))
            .in_("status", ["active", "monitoring", "escalated"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("recovery_score: cases query failed | patient=%s", patient_id)
        cases_res = type("_R", (), {"data": []})()

    if not cases_res.data:
        return {
            "score":        50,
            "risk_state":   "warning",
            "trend":        "stable",
            "last_updated": _iso(None),
        }

    case_id = str(cases_res.data[0]["case_id"])
    score   = 50

    # -----------------------------------------------------------------
    # Step 1 — monitoring adherence bonus  (max +20)
    # -----------------------------------------------------------------
    monitoring_bonus = 0
    try:
        plans_res = (
            await db.table(_TBL_MON_PLANS)
            .select("checkpoints")
            .eq("case_id", case_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if plans_res.data:
            checkpoints = plans_res.data[0].get("checkpoints") or []
            if isinstance(checkpoints, list) and checkpoints:
                responded = sum(1 for cp in checkpoints
                                if isinstance(cp, dict) and cp.get("status") == "responded")
                monitoring_bonus = int((responded / len(checkpoints)) * 20)
    except Exception:
        logger.exception("recovery_score: adherence query failed | case=%s", case_id)

    # -----------------------------------------------------------------
    # Step 2 — lab trajectory bonus  (+15 / 0 / -15)
    # -----------------------------------------------------------------
    lab_bonus  = 0
    lab_trend  = "stable"
    try:
        tl_res = (
            await db.table(_TBL_TIMELINE)
            .select("content,event_date")
            .eq("case_id", case_id)
            .eq("event_type", "agent_synthesis")
            .order("event_date", desc=True)
            .limit(10)
            .execute()
        )
        deepdive_rows = [
            r for r in tl_res.data
            if isinstance(r.get("content"), dict) and "risk_score" in r["content"]
        ]
        if len(deepdive_rows) >= 2:
            latest_rank   = _RISK_RANK.get(str(deepdive_rows[0]["content"]["risk_score"]).lower(), 2)
            previous_rank = _RISK_RANK.get(str(deepdive_rows[1]["content"]["risk_score"]).lower(), 2)
            if latest_rank > previous_rank:      # higher rank = healthier
                lab_bonus = +15
                lab_trend = "improving"
            elif latest_rank < previous_rank:
                lab_bonus = -15
                lab_trend = "deteriorating"
    except Exception:
        logger.exception("recovery_score: lab trajectory query failed | case=%s", case_id)

    # -----------------------------------------------------------------
    # Step 3 — days-stable bonus  (-20 / 0 / +5 / +10)
    # -----------------------------------------------------------------
    stable_bonus = 0
    try:
        esc_res = (
            await db.table(_TBL_TIMELINE)
            .select("event_date")
            .eq("case_id", case_id)
            .eq("event_type", "escalation")
            .order("event_date", desc=True)
            .limit(1)
            .execute()
        )
        if esc_res.data:
            last_esc = _dt_parse(esc_res.data[0].get("event_date"))
            if last_esc:
                days = (datetime.now(tz=timezone.utc) - last_esc).days
                if days == 0:
                    stable_bonus = -20
                elif days == 1:
                    stable_bonus = 0
                elif days == 2:
                    stable_bonus = +5
                else:
                    stable_bonus = +10
        else:
            # No escalation ever recorded → patient is stable
            stable_bonus = +10
    except Exception:
        logger.exception("recovery_score: days-stable query failed | case=%s", case_id)

    # -----------------------------------------------------------------
    # Final score
    # -----------------------------------------------------------------
    score = max(0, min(100, score + monitoring_bonus + lab_bonus + stable_bonus))

    if score >= 75:
        risk_state = "stable"
    elif score >= 50:
        risk_state = "warning"
    else:
        risk_state = "critical"

    return {
        "score":        score,
        "risk_state":   risk_state,
        "trend":        lab_trend,
        "last_updated": _iso(None),
    }


# ---------------------------------------------------------------------------
# ENDPOINT 4: GET /console/escalations
# ---------------------------------------------------------------------------

@router.get("/console/escalations")
async def console_escalations() -> dict:
    """
    Return all unresolved escalations across all cases, sorted by a
    composite severity + recency score (highest urgency first).

    Joins escalations → cases → patients in Python via batch DB calls.
    """
    db = await get_client()

    # -----------------------------------------------------------------
    # Fetch raw escalations (unresolved)
    # -----------------------------------------------------------------
    try:
        esc_res = (
            await db.table(_TBL_ESCALATE)
            .select("*")
            .eq("resolved", False)
            .order("created_at", desc=True)
            .execute()
        )
        raw_escalations: list[dict] = esc_res.data or []
    except Exception:
        logger.exception("console_escalations: escalation query failed")
        return {"escalations": []}

    if not raw_escalations:
        return {"escalations": []}

    # -----------------------------------------------------------------
    # Batch-fetch cases and patients to avoid N+1 queries
    # -----------------------------------------------------------------
    case_ids    = list({str(e["case_id"]) for e in raw_escalations if e.get("case_id")})
    patient_ids = list({str(e["patient_id"]) for e in raw_escalations if e.get("patient_id")})

    cases_by_id:    dict[str, dict] = {}
    patients_by_id: dict[str, dict] = {}

    try:
        if case_ids:
            c_res = (
                await db.table(_TBL_CASES)
                .select("case_id,patient_id,created_at,status")
                .in_("case_id", case_ids)
                .execute()
            )
            cases_by_id = {str(r["case_id"]): r for r in c_res.data}
    except Exception:
        logger.exception("console_escalations: cases batch-fetch failed")

    try:
        if patient_ids:
            p_res = (
                await db.table(_TBL_PATIENTS)
                .select("patient_id,name,age,sex")
                .in_("patient_id", patient_ids)
                .execute()
            )
            patients_by_id = {str(r["patient_id"]): r for r in p_res.data}
    except Exception:
        logger.exception("console_escalations: patients batch-fetch failed")

    # -----------------------------------------------------------------
    # Build response rows with composite sort score
    # -----------------------------------------------------------------
    now   = datetime.now(tz=timezone.utc)
    rows: list[dict] = []

    for esc in raw_escalations:
        severity_raw    = str(esc.get("severity", "watch"))
        severity_score  = _SEV_SCORE.get(severity_raw, 25)

        created = _dt_parse(esc.get("created_at"))
        hours_since     = int((now - created).total_seconds() / 3600) if created else 48
        recency_score   = max(0, 48 - hours_since)
        composite       = severity_score + recency_score

        case  = cases_by_id.get(str(esc.get("case_id") or ""))
        pat   = patients_by_id.get(str(esc.get("patient_id") or ""))

        case_created = _dt_parse(case.get("created_at")) if case else None
        case_day     = (now - case_created).days if case_created else 0

        # Derive trigger_source from stored trigger_evidence dict
        evidence = esc.get("trigger_evidence") or {}
        kw       = evidence.get("keyword_signals") if isinstance(evidence, dict) else {}
        criteria = evidence.get("criteria_matched") if isinstance(evidence, dict) else {}
        groq     = evidence.get("groq_assessment") if isinstance(evidence, dict) else None

        if isinstance(kw, dict) and kw.get("has_emergency"):
            trigger_source = "keyword"
        elif isinstance(criteria, dict) and criteria.get("escalate_matches"):
            trigger_source = "checkpoint"
        elif groq:
            trigger_source = "groq"
        else:
            trigger_source = "checkpoint"

        rows.append({
            "id":             str(esc.get("escalation_id") or esc.get("id") or ""),
            "patient_name":   pat["name"]   if pat else "Unknown",
            "patient_age":    pat["age"]    if pat and pat.get("age") is not None else 0,
            "patient_sex":    pat["sex"]    if pat and pat.get("sex") else "unknown",
            "case_id":        str(esc.get("case_id") or ""),
            "case_day":       case_day,
            "severity":       _SEV_DISPLAY.get(severity_raw, "warning"),
            "trigger_reason": str(esc.get("trigger_reason") or ""),
            "trigger_source": trigger_source,
            "created_at":     _iso(esc.get("created_at")),
            "composite_score": composite,
        })

    rows.sort(key=lambda r: r["composite_score"], reverse=True)
    return {"escalations": rows}


# ---------------------------------------------------------------------------
# ENDPOINT 5: GET /console/agent-activity
# ---------------------------------------------------------------------------

@router.get("/console/agent-activity")
async def console_agent_activity(
    case_id: str | None = Query(default=None, description="Filter by case_id"),
) -> dict:
    """
    Return the last 30 agent activity records, optionally filtered by case.

    Joins agent_activity → cases → patients to resolve patient_name.
    Returns empty activity list (not an error) if the agent_activity table
    doesn't exist yet (migration not yet run).
    """
    db = await get_client()

    # -----------------------------------------------------------------
    # Fetch agent activity rows
    # -----------------------------------------------------------------
    try:
        query = (
            db.table(_TBL_AGENT_ACT)
            .select("*")
            .order("created_at", desc=True)
            .limit(30)
        )
        if case_id:
            query = query.eq("case_id", case_id)
        act_res   = await query.execute()
        raw_rows: list[dict] = act_res.data or []
    except Exception:
        # Table may not exist yet if migration hasn't been run
        logger.warning("console_agent_activity: agent_activity query failed (table may be missing)")
        return {"activity": []}

    if not raw_rows:
        return {"activity": []}

    # -----------------------------------------------------------------
    # Batch-resolve patient names via cases → patients
    # -----------------------------------------------------------------
    activity_case_ids = list({str(r["case_id"]) for r in raw_rows if r.get("case_id")})

    cases_map:    dict[str, dict] = {}
    patients_map: dict[str, dict] = {}

    try:
        if activity_case_ids:
            c_res = (
                await db.table(_TBL_CASES)
                .select("case_id,patient_id")
                .in_("case_id", activity_case_ids)
                .execute()
            )
            cases_map = {str(r["case_id"]): r for r in c_res.data}

            patient_id_list = list({str(r["patient_id"]) for r in c_res.data if r.get("patient_id")})
            if patient_id_list:
                p_res = (
                    await db.table(_TBL_PATIENTS)
                    .select("patient_id,name")
                    .in_("patient_id", patient_id_list)
                    .execute()
                )
                patients_map = {str(r["patient_id"]): r for r in p_res.data}
    except Exception:
        logger.exception("console_agent_activity: join query failed")

    # -----------------------------------------------------------------
    # Build response rows
    # -----------------------------------------------------------------
    activity: list[dict] = []
    for row in raw_rows:
        case      = cases_map.get(str(row.get("case_id") or ""))
        patient   = patients_map.get(str(case["patient_id"]) if case else "") if case else None
        activity.append({
            "id":           str(row.get("id") or ""),
            "case_id":      str(row.get("case_id") or ""),
            "patient_name": patient["name"] if patient else "Unknown",
            "agent_name":   str(row.get("agent_name") or ""),
            "action":       str(row.get("action") or ""),
            "finding":      str(row.get("finding") or ""),
            "created_at":   _iso(row.get("created_at")),
        })

    return {"activity": activity}
