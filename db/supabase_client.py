"""
ClinIQ 2.0 async database client.

Single source of truth for all Supabase interactions.  Every public function
maps to one logical operation, is fully typed, and re-raises on failure after
logging — callers decide how to handle errors.
"""

import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from dotenv import load_dotenv
from supabase import AsyncClient, create_async_client

# ---------------------------------------------------------------------------
# Load .env before any os.environ.get() calls.
#
# WHY HERE: Python executes module-level code at import time. If this module
# is imported before the application entry point has called load_dotenv()
# (e.g. via workers.watch_worker → db.supabase_client before config.py runs),
# the os.environ.get() calls below would return "" and raise EnvironmentError.
#
# Using __file__ to resolve the project root makes this safe regardless of
# the process working directory. load_dotenv() is a no-op when .env is absent
# (e.g. HuggingFace Spaces, where secrets are injected directly into the env).
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from db.models import (
    AgentNote,
    Case,
    Checkpoint,
    CreateCaseRequest,
    CreatePatientRequest,
    Escalation,
    LabReport,
    MonitoringPlan,
    Patient,
    Task,
    TimelineEvent,
    UpdateCaseRiskRequest,
    WhatsappMessage,
)

logger = logging.getLogger("cliniq.db")

# ---------------------------------------------------------------------------
# Environment validation (fail fast at import time)
# ---------------------------------------------------------------------------

_SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
_SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

if not _SUPABASE_URL:
    raise EnvironmentError("SUPABASE_URL environment variable is not set")
if not _SUPABASE_KEY:
    raise EnvironmentError("SUPABASE_KEY environment variable is not set")

# ---------------------------------------------------------------------------
# Table name constants
# ---------------------------------------------------------------------------

TABLE_CLINICS = "clinics"
TABLE_PATIENTS = "patients"
TABLE_CASES = "cases"
TABLE_TIMELINE_EVENTS = "timeline_events"
TABLE_LAB_REPORTS = "lab_reports"
TABLE_MONITORING_PLANS = "monitoring_plans"
TABLE_TASKS = "tasks"
TABLE_WHATSAPP_MESSAGES = "whatsapp_messages"
TABLE_ESCALATIONS = "escalations"

# ---------------------------------------------------------------------------
# Singleton async client
# ---------------------------------------------------------------------------

_client: AsyncClient | None = None


async def get_client() -> AsyncClient:
    """Return the shared AsyncClient, initialising it on first call."""
    global _client
    if _client is None:
        try:
            _client = await create_async_client(_SUPABASE_URL, _SUPABASE_KEY)
            logger.info("Supabase async client initialised")
        except Exception:
            logger.exception("Failed to initialise Supabase async client")
            raise
    return _client


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

# Insert a new patient row and return the full persisted model
async def create_patient(data: CreatePatientRequest) -> Patient:
    try:
        db = await get_client()
        payload = data.model_dump(mode="json", exclude_none=True)
        res = await db.table(TABLE_PATIENTS).insert(payload).execute()
        return Patient(**res.data[0])
    except Exception:
        logger.exception("create_patient failed")
        raise


# Look up a patient by primary key
async def get_patient(patient_id: UUID) -> Patient | None:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_PATIENTS)
            .select("*")
            .eq("patient_id", str(patient_id))
            .execute()
        )
        return Patient(**res.data[0]) if res.data else None
    except Exception:
        logger.exception("get_patient failed for patient_id=%s", patient_id)
        raise


# Look up a patient by their unique phone number
async def get_patient_by_phone(phone: str) -> Patient | None:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_PATIENTS)
            .select("*")
            .eq("phone", phone)
            .execute()
        )
        return Patient(**res.data[0]) if res.data else None
    except Exception:
        logger.exception("get_patient_by_phone failed for phone=%s", phone)
        raise


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

# Open a new clinical case for a patient
async def create_case(data: CreateCaseRequest) -> Case:
    try:
        db = await get_client()
        payload = data.model_dump(mode="json", exclude_none=True)
        res = await db.table(TABLE_CASES).insert(payload).execute()
        return Case(**res.data[0])
    except Exception:
        logger.exception("create_case failed")
        raise


# Fetch a single case by primary key
async def get_case(case_id: UUID) -> Case | None:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_CASES)
            .select("*")
            .eq("case_id", str(case_id))
            .execute()
        )
        return Case(**res.data[0]) if res.data else None
    except Exception:
        logger.exception("get_case failed for case_id=%s", case_id)
        raise


# Return all open/monitoring/escalated cases for a clinic, newest first
async def get_active_cases_for_clinic(clinic_id: UUID) -> list[Case]:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_CASES)
            .select("*")
            .eq("clinic_id", str(clinic_id))
            .in_("status", ["active", "monitoring", "escalated"])
            .order("updated_at", desc=True)
            .execute()
        )
        return [Case(**row) for row in res.data]
    except Exception:
        logger.exception("get_active_cases_for_clinic failed for clinic_id=%s", clinic_id)
        raise


# Overwrite risk tier and flags on a case
async def update_case_risk(case_id: UUID, request: UpdateCaseRiskRequest) -> None:
    try:
        db = await get_client()
        payload = {
            "risk_tier": request.risk_tier,
            "risk_flags": request.risk_flags,
            "updated_at": datetime.utcnow().isoformat(),
        }
        await db.table(TABLE_CASES).update(payload).eq("case_id", str(case_id)).execute()
    except Exception:
        logger.exception("update_case_risk failed for case_id=%s", case_id)
        raise


# Transition a case to a new status
async def update_case_status(
    case_id: UUID,
    status: Literal["active", "monitoring", "resolved", "escalated"],
) -> None:
    try:
        db = await get_client()
        payload = {"status": status, "updated_at": datetime.utcnow().isoformat()}
        await db.table(TABLE_CASES).update(payload).eq("case_id", str(case_id)).execute()
    except Exception:
        logger.exception("update_case_status failed for case_id=%s", case_id)
        raise


# Append one AgentNote to cases.agent_notes without clobbering existing notes
async def append_agent_note(case_id: UUID, note: AgentNote) -> None:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_CASES)
            .select("agent_notes")
            .eq("case_id", str(case_id))
            .execute()
        )
        notes: list = res.data[0]["agent_notes"] if res.data else []
        notes.append(note.model_dump(mode="json"))
        await db.table(TABLE_CASES).update(
            {"agent_notes": notes, "updated_at": datetime.utcnow().isoformat()}
        ).eq("case_id", str(case_id)).execute()
    except Exception:
        logger.exception("append_agent_note failed for case_id=%s", case_id)
        raise


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

# Write a single immutable event to the case timeline
async def write_timeline_event(
    case_id: UUID,
    event_type: str,
    title: str,
    content: dict,
    source: str,
    event_date: datetime | None = None,
) -> TimelineEvent:
    try:
        db = await get_client()
        payload = {
            "case_id": str(case_id),
            "event_type": event_type,
            "title": title,
            "content": content,
            "source": source,
            "event_date": (event_date or datetime.utcnow()).isoformat(),
        }
        res = await db.table(TABLE_TIMELINE_EVENTS).insert(payload).execute()
        return TimelineEvent(**res.data[0])
    except Exception:
        logger.exception("write_timeline_event failed for case_id=%s", case_id)
        raise


# Return the full ordered timeline for a case
async def get_timeline(case_id: UUID) -> list[TimelineEvent]:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_TIMELINE_EVENTS)
            .select("*")
            .eq("case_id", str(case_id))
            .order("event_date", desc=False)
            .execute()
        )
        return [TimelineEvent(**row) for row in res.data]
    except Exception:
        logger.exception("get_timeline failed for case_id=%s", case_id)
        raise


# ---------------------------------------------------------------------------
# Lab Reports
# ---------------------------------------------------------------------------

# Persist a lab report and return it with the generated report_id
async def save_lab_report(report: LabReport) -> LabReport:
    try:
        db = await get_client()
        payload = report.model_dump(mode="json", exclude_none=True)
        res = await db.table(TABLE_LAB_REPORTS).insert(payload).execute()
        return LabReport(**res.data[0])
    except Exception:
        logger.exception("save_lab_report failed for case_id=%s", report.case_id)
        raise


# Store the agent deep-dive output on an existing lab report
async def update_lab_report_deepdive(report_id: UUID, deep_dive_output: dict) -> None:
    try:
        db = await get_client()
        await db.table(TABLE_LAB_REPORTS).update(
            {"deep_dive_output": deep_dive_output}
        ).eq("report_id", str(report_id)).execute()
    except Exception:
        logger.exception("update_lab_report_deepdive failed for report_id=%s", report_id)
        raise


# Persist the full structured analysis: extracted values, abnormal flags, and DeepDive output
async def update_lab_report_analysis(
    report_id: UUID,
    parsed_values: dict,
    abnormal_flags: list[dict],
    deep_dive_output: dict,
) -> None:
    try:
        db = await get_client()
        await db.table(TABLE_LAB_REPORTS).update(
            {
                "parsed_values":   parsed_values,
                "abnormal_flags":  abnormal_flags,
                "deep_dive_output": deep_dive_output,
            }
        ).eq("report_id", str(report_id)).execute()
    except Exception:
        logger.exception("update_lab_report_analysis failed for report_id=%s", report_id)
        raise


# Return all lab reports for a case, most recent first
async def get_lab_reports(case_id: UUID) -> list[LabReport]:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_LAB_REPORTS)
            .select("*")
            .eq("case_id", str(case_id))
            .order("uploaded_at", desc=True)
            .execute()
        )
        return [LabReport(**row) for row in res.data]
    except Exception:
        logger.exception("get_lab_reports failed for case_id=%s", case_id)
        raise


# ---------------------------------------------------------------------------
# Monitoring Plans
# ---------------------------------------------------------------------------

# Persist a new monitoring plan and return it with the generated plan_id
async def create_monitoring_plan(plan: MonitoringPlan) -> MonitoringPlan:
    try:
        db = await get_client()
        payload = plan.model_dump(mode="json", exclude_none=True)
        res = await db.table(TABLE_MONITORING_PLANS).insert(payload).execute()
        return MonitoringPlan(**res.data[0])
    except Exception:
        logger.exception("create_monitoring_plan failed for case_id=%s", plan.case_id)
        raise


# Return every active monitoring plan — called daily by the Watch Worker
async def get_active_monitoring_plans() -> list[MonitoringPlan]:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_MONITORING_PLANS)
            .select("*")
            .eq("status", "active")
            .execute()
        )
        return [MonitoringPlan(**row) for row in res.data]
    except Exception:
        logger.exception("get_active_monitoring_plans failed")
        raise


# Return (plan, checkpoint) pairs whose scheduled_date is today and still pending
async def get_due_checkpoints_today() -> list[tuple[MonitoringPlan, Checkpoint]]:
    try:
        today = date.today().isoformat()
        plans = await get_active_monitoring_plans()
        due: list[tuple[MonitoringPlan, Checkpoint]] = []
        for plan in plans:
            for checkpoint in plan.checkpoints:
                if (
                    checkpoint.status == "pending"
                    and checkpoint.scheduled_date.isoformat() == today
                ):
                    due.append((plan, checkpoint))
        return due
    except Exception:
        logger.exception("get_due_checkpoints_today failed")
        raise


# Mutate one checkpoint in the JSONB array identified by day_offset
async def update_checkpoint(
    plan_id: UUID,
    day_offset: int,
    status: str,
    patient_response: str | None = None,
    agent_evaluation: dict | None = None,
    whatsapp_message_id: str | None = None,
) -> None:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_MONITORING_PLANS)
            .select("checkpoints")
            .eq("plan_id", str(plan_id))
            .execute()
        )
        checkpoints: list[dict] = res.data[0]["checkpoints"] if res.data else []
        for cp in checkpoints:
            if cp["day_offset"] == day_offset:
                cp["status"] = status
                if patient_response is not None:
                    cp["patient_response"] = patient_response
                if agent_evaluation is not None:
                    cp["agent_evaluation"] = agent_evaluation
                if whatsapp_message_id is not None:
                    cp["whatsapp_message_id"] = whatsapp_message_id
                break
        await db.table(TABLE_MONITORING_PLANS).update(
            {"checkpoints": checkpoints, "updated_at": datetime.utcnow().isoformat()}
        ).eq("plan_id", str(plan_id)).execute()
    except Exception:
        logger.exception(
            "update_checkpoint failed for plan_id=%s day_offset=%s", plan_id, day_offset
        )
        raise


# Mark a monitoring plan as completed
async def complete_monitoring_plan(plan_id: UUID) -> None:
    try:
        db = await get_client()
        payload = {"status": "completed", "updated_at": datetime.utcnow().isoformat()}
        await db.table(TABLE_MONITORING_PLANS).update(payload).eq("plan_id", str(plan_id)).execute()
    except Exception:
        logger.exception("complete_monitoring_plan failed for plan_id=%s", plan_id)
        raise


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

# Persist a new task and return it with the generated task_id
async def create_task(task: Task) -> Task:
    try:
        db = await get_client()
        payload = task.model_dump(mode="json", exclude_none=True)
        res = await db.table(TABLE_TASKS).insert(payload).execute()
        return Task(**res.data[0])
    except Exception:
        logger.exception("create_task failed for case_id=%s", task.case_id)
        raise


# Return pending/sent tasks for a case ordered by due date ascending
async def get_pending_tasks(case_id: UUID) -> list[Task]:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_TASKS)
            .select("*")
            .eq("case_id", str(case_id))
            .in_("status", ["pending", "sent"])
            .order("due_date", desc=False)
            .execute()
        )
        return [Task(**row) for row in res.data]
    except Exception:
        logger.exception("get_pending_tasks failed for case_id=%s", case_id)
        raise


# Mark a task completed and stamp the completion time
async def mark_task_complete(task_id: UUID) -> None:
    try:
        db = await get_client()
        payload = {"status": "completed", "completed_at": datetime.utcnow().isoformat()}
        await db.table(TABLE_TASKS).update(payload).eq("task_id", str(task_id)).execute()
    except Exception:
        logger.exception("mark_task_complete failed for task_id=%s", task_id)
        raise


# Return all pending tasks whose due_date has passed — used by Watch Worker
async def get_overdue_tasks() -> list[Task]:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_TASKS)
            .select("*")
            .lt("due_date", date.today().isoformat())
            .eq("status", "pending")
            .execute()
        )
        return [Task(**row) for row in res.data]
    except Exception:
        logger.exception("get_overdue_tasks failed")
        raise


# ---------------------------------------------------------------------------
# WhatsApp Messages
# ---------------------------------------------------------------------------

# Persist a WhatsApp message and return it with the generated message_id
async def save_whatsapp_message(msg: WhatsappMessage) -> WhatsappMessage:
    try:
        db = await get_client()
        payload = msg.model_dump(mode="json", exclude_none=True)
        res = await db.table(TABLE_WHATSAPP_MESSAGES).insert(payload).execute()
        return WhatsappMessage(**res.data[0])
    except Exception:
        logger.exception("save_whatsapp_message failed for case_id=%s", msg.case_id)
        raise


# Return inbound messages not yet processed by the response agent
async def get_unprocessed_inbound_messages() -> list[WhatsappMessage]:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_WHATSAPP_MESSAGES)
            .select("*")
            .eq("direction", "inbound")
            .eq("processed", False)
            .execute()
        )
        return [WhatsappMessage(**row) for row in res.data]
    except Exception:
        logger.exception("get_unprocessed_inbound_messages failed")
        raise


# Flag a message as processed and store the agent's evaluation
async def mark_message_processed(message_id: UUID, agent_evaluation: dict) -> None:
    try:
        db = await get_client()
        payload = {"processed": True, "agent_evaluation": agent_evaluation}
        await db.table(TABLE_WHATSAPP_MESSAGES).update(payload).eq(
            "message_id", str(message_id)
        ).execute()
    except Exception:
        logger.exception("mark_message_processed failed for message_id=%s", message_id)
        raise


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------

# Persist an escalation and automatically flip the parent case to 'escalated'
async def create_escalation(escalation: Escalation) -> Escalation:
    try:
        db = await get_client()
        payload = escalation.model_dump(mode="json", exclude_none=True)
        res = await db.table(TABLE_ESCALATIONS).insert(payload).execute()
        created = Escalation(**res.data[0])
        await update_case_status(created.case_id, "escalated")
        return created
    except Exception:
        logger.exception("create_escalation failed for case_id=%s", escalation.case_id)
        raise


# Return all unresolved escalations across a clinic's cases, newest first
async def get_unresolved_escalations(clinic_id: UUID) -> list[Escalation]:
    try:
        db = await get_client()
        cases_res = (
            await db.table(TABLE_CASES)
            .select("case_id")
            .eq("clinic_id", str(clinic_id))
            .execute()
        )
        case_ids = [row["case_id"] for row in cases_res.data]
        if not case_ids:
            return []
        res = (
            await db.table(TABLE_ESCALATIONS)
            .select("*")
            .in_("case_id", case_ids)
            .eq("resolved", False)
            .order("created_at", desc=True)
            .execute()
        )
        return [Escalation(**row) for row in res.data]
    except Exception:
        logger.exception("get_unresolved_escalations failed for clinic_id=%s", clinic_id)
        raise


# Mark an escalation resolved and stamp the resolution time
async def resolve_escalation(escalation_id: UUID) -> None:
    try:
        db = await get_client()
        payload = {"resolved": True, "resolved_at": datetime.utcnow().isoformat()}
        await db.table(TABLE_ESCALATIONS).update(payload).eq(
            "escalation_id", str(escalation_id)
        ).execute()
    except Exception:
        logger.exception("resolve_escalation failed for escalation_id=%s", escalation_id)
        raise


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

# Aggregate case counts and risk distribution for the doctor dashboard
async def get_case_summary_for_clinic(clinic_id: UUID) -> dict:
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_CASES)
            .select("status, risk_tier")
            .eq("clinic_id", str(clinic_id))
            .execute()
        )
        rows = res.data
        return {
            "total_active": sum(1 for r in rows if r["status"] == "active"),
            "total_monitoring": sum(1 for r in rows if r["status"] == "monitoring"),
            "total_escalated": sum(1 for r in rows if r["status"] == "escalated"),
            "total_resolved": sum(1 for r in rows if r["status"] == "resolved"),
            "high_risk_count": sum(1 for r in rows if r["risk_tier"] == "high"),
            "critical_risk_count": sum(1 for r in rows if r["risk_tier"] == "critical"),
        }
    except Exception:
        logger.exception("get_case_summary_for_clinic failed for clinic_id=%s", clinic_id)
        raise
