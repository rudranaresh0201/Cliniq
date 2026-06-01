"""
db/timeline.py — fire-and-forget timeline + agent_activity writer.

Used by agents and workers to append structured events after their core
operations complete.  All writes are wrapped in try/except so a DB hiccup
or missing case_id never propagates to the calling agent or worker.

Usage:
    from db.timeline import write_timeline_event as _tl_write

    await _tl_write(
        case_id    = str(case.case_id),    # None → silently skipped
        event_type = "deepdive_complete",
        payload    = {...},
        agent_name = "CBCInterpreter",
    )

Tables written:
    timeline_events  — one row per event (uses 'agent_synthesis' or nearest Literal)
    agent_activity   — one row per event (free-form, no Literal constraint)

SQL for agent_activity (run once in Supabase SQL editor):
    CREATE TABLE IF NOT EXISTS agent_activity (
        id          UUID         DEFAULT gen_random_uuid() PRIMARY KEY,
        case_id     UUID         REFERENCES cases(case_id),
        agent_name  TEXT         NOT NULL,
        action      TEXT         NOT NULL,
        finding     TEXT,
        created_at  TIMESTAMPTZ  DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS agent_activity_case_created
        ON agent_activity(case_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS agent_activity_created
        ON agent_activity(created_at DESC);
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("cliniq.db.timeline")

# ---------------------------------------------------------------------------
# Table name constants
# ---------------------------------------------------------------------------

_TABLE_TIMELINE_EVENTS = "timeline_events"
_TABLE_AGENT_ACTIVITY  = "agent_activity"

# ---------------------------------------------------------------------------
# event_type → timeline_events.event_type Literal mapping
#
# The timeline_events.event_type column is constrained to a fixed Literal in
# the Pydantic model.  The DB column itself may not enforce a CHECK constraint,
# but we map safely to avoid surprises.
# ---------------------------------------------------------------------------

_TL_TYPE_MAP: dict[str, str] = {
    "deepdive_complete":    "agent_synthesis",
    "checkpoint_sent":      "whatsapp_checkin",
    "checkpoint_answered":  "whatsapp_checkin",
    "escalation_triggered": "escalation",
    "symptom_reported":     "symptom_report",
    "monitoring_created":   "agent_synthesis",
}


# ---------------------------------------------------------------------------
# One-sentence finding builder for agent_activity.finding
# ---------------------------------------------------------------------------

def _finding_sentence(event_type: str, payload: dict) -> str:
    """Return a human-readable one-liner from a payload dict."""
    if event_type == "deepdive_complete":
        rt   = payload.get("report_type", "report")
        risk = payload.get("risk_score", "unknown")
        spec = payload.get("specialist", "")
        return f"{rt} analysis complete ({spec}) — risk: {risk}."

    if event_type == "checkpoint_sent":
        day = payload.get("checkpoint_day", payload.get("checkpoint_number", "?"))
        n   = payload.get("questions_sent", 0)
        return f"Day-{day} checkpoint message sent with {n} question(s)."

    if event_type == "checkpoint_answered":
        summary   = payload.get("response_summary", "Patient responded.")
        triggered = payload.get("escalation_triggered", False)
        suffix    = " Escalation triggered." if triggered else " No escalation."
        return f"{summary}{suffix}"

    if event_type == "escalation_triggered":
        reason   = payload.get("trigger_reason", "")
        severity = payload.get("severity", "")
        return f"Escalation ({severity}): {reason}"

    if event_type == "symptom_reported":
        dx   = payload.get("top_diagnosis", "unknown")
        conf = payload.get("top_confidence", 0.0)
        pct  = int(float(conf) * 100) if conf else 0
        return f"Symptom analysis complete — top hypothesis: {dx} ({pct}%)."

    if event_type == "monitoring_created":
        name = payload.get("protocol_name", "")
        days = payload.get("duration_days", 0)
        cps  = payload.get("total_checkpoints", 0)
        return f"{name} monitoring protocol created: {cps} checkpoints over {days} days."

    return f"{event_type.replace('_', ' ')} recorded."


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

async def write_timeline_event(
    case_id:    str | None,
    event_type: str,
    payload:    dict,
    agent_name: str,
) -> None:
    """
    Insert one row into timeline_events and one row into agent_activity.

    Returns None unconditionally — never raises.  A missing case_id causes
    a debug-level log and an early return; all other failures are logged at
    ERROR level and silently swallowed.
    """
    if not case_id:
        logger.debug(
            "write_timeline_event: no case_id — skipping | event_type=%s agent=%s",
            event_type, agent_name,
        )
        return

    try:
        from db.supabase_client import get_client   # local import avoids circular deps

        db  = await get_client()
        now = datetime.now(tz=timezone.utc).isoformat()

        tl_type  = _TL_TYPE_MAP.get(event_type, "agent_synthesis")
        tl_title = f"{agent_name}: {event_type.replace('_', ' ')}"
        finding  = _finding_sentence(event_type, payload)
        action   = event_type.replace("_", " ")

        # 1 — timeline_events
        tl_response = await (
            db.table(_TABLE_TIMELINE_EVENTS)
            .insert({
                "case_id":    case_id,
                "event_type": tl_type,
                "title":      tl_title,
                "content":    payload,
                "source":     "agent",
                "event_date": now,
            })
            .execute()
        )
        # 2 — agent_activity
        aa_response = await (
            db.table(_TABLE_AGENT_ACTIVITY)
            .insert({
                "case_id":    case_id,
                "agent_name": agent_name,
                "action":     action,
                "finding":    finding,
                "created_at": now,
            })
            .execute()
        )
        logger.debug(
            "write_timeline_event OK | case=%s event_type=%s agent=%s",
            case_id, event_type, agent_name,
        )

    except Exception as e:
        logger.exception(
            "write_timeline_event failed (non-fatal) | case=%s event_type=%s agent=%s",
            case_id, event_type, agent_name,
        )
