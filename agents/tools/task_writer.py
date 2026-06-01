"""
ClinIQ 2.0 — task_writer tool.

Replaces the registry stub.  Converts structured clinical recommendations
(lab tests and medications) from clinical_reasoner output into Task rows
in Supabase with due dates, priorities, and WhatsApp reminder channels.

Every generated case also receives one follow-up consultation task so that
no patient falls through the cracks regardless of which other tasks are
ordered.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from db.models import Task
from db.supabase_client import create_task

logger = logging.getLogger("cliniq.tools.task_writer")

# ---------------------------------------------------------------------------
# Priority mapping constants — edit here when clinical urgency rules change
# ---------------------------------------------------------------------------

PRIORITY_DUE_DATE_MAP: dict[str, int] = {
    "immediate":   0,   # today — start/get done immediately
    "within_48h":  2,   # 2 days
    "within_week": 7,   # 7 days
    "routine":     14,  # 14 days
}

PRIORITY_TASK_LEVEL_MAP: dict[str, str] = {
    "immediate":   "urgent",
    "within_48h":  "high",
    "within_week": "medium",
    "routine":     "low",
}

_DEFAULT_CLINICAL_PRIORITY = "within_week"
_DEFAULT_CREATED_BY = "clinical_reasoner_agent"
_DEFAULT_FOLLOW_UP_DAYS = 7


# ---------------------------------------------------------------------------
# Fallback return value
# ---------------------------------------------------------------------------


def _empty_result(error: str) -> dict:
    return {
        "tasks_created": 0,
        "tasks_failed": 0,
        "task_ids": [],
        "task_breakdown": {"lab_tests": 0, "medications": 0, "followups": 0},
        "earliest_due": "",
        "latest_due": "",
        "error": error,
    }


# ---------------------------------------------------------------------------
# Task builders
# ---------------------------------------------------------------------------


def _build_test_task(
    case_uuid: UUID,
    item: dict,
    created_by: str,
) -> Task | None:
    """Build a lab_test Task from a recommended_tests entry."""
    test_name = item.get("test", "").strip()
    if not test_name:
        logger.warning("task_writer: skipping test item with missing 'test' key")
        return None

    reason = item.get("reason", "")
    priority_str = item.get("priority", _DEFAULT_CLINICAL_PRIORITY)
    days_offset = PRIORITY_DUE_DATE_MAP.get(priority_str, 7)
    due_date = (datetime.now(tz=timezone.utc) + timedelta(days=days_offset)).date()
    task_priority = PRIORITY_TASK_LEVEL_MAP.get(priority_str, "medium")

    description = f"Get {test_name} done"
    if reason:
        description += f" — {reason}"

    return Task(
        case_id=case_uuid,
        task_type="lab_test",
        description=description,
        due_date=due_date,
        priority=task_priority,  # type: ignore[arg-type]
        status="pending",
        reminder_channel="whatsapp",
        created_by=created_by,
    )


def _build_medication_task(
    case_uuid: UUID,
    item: dict,
    today,
    created_by: str,
) -> Task | None:
    """Build a medication Task from a recommended_medications entry."""
    drug = item.get("drug", "").strip()
    if not drug:
        logger.warning("task_writer: skipping medication item with missing 'drug' key")
        return None

    indication = item.get("indication", "")
    note = item.get("note", "").strip()

    description = f"Start {drug} for {indication}"
    if note:
        description += f". Note: {note}"

    return Task(
        case_id=case_uuid,
        task_type="medication",
        description=description,
        due_date=today,
        priority="high",
        status="pending",
        reminder_channel="whatsapp",
        created_by=created_by,
    )


def _build_followup_task(
    case_uuid: UUID,
    today,
    follow_up_days: int,
    created_by: str,
) -> Task:
    """Build the mandatory follow-up consultation task."""
    return Task(
        case_id=case_uuid,
        task_type="followup",
        description="Follow-up consultation — review symptoms and test results",
        due_date=today + timedelta(days=follow_up_days),
        priority="medium",
        status="pending",
        reminder_channel="whatsapp",
        created_by=created_by,
    )


# ---------------------------------------------------------------------------
# Main tool function
# ---------------------------------------------------------------------------


async def write_tasks(inputs: dict) -> dict:
    """
    Convert clinical_reasoner recommendations into persisted Supabase tasks.

    Each task is saved independently — a single save failure never prevents
    the remaining tasks from being created.  Always appends a follow-up
    consultation task regardless of how many other tasks are created.
    """
    case_id_str: str = inputs.get("case_id", "")
    recommended_tests: list[dict] = inputs.get("recommended_tests", [])
    recommended_medications: list[dict] = inputs.get("recommended_medications", [])
    follow_up_days: int = int(inputs.get("follow_up_days", _DEFAULT_FOLLOW_UP_DAYS))
    created_by: str = inputs.get("created_by", _DEFAULT_CREATED_BY)

    logger.info(
        "write_tasks | case=%s | tests=%d | medications=%d | follow_up_days=%d",
        case_id_str,
        len(recommended_tests),
        len(recommended_medications),
        follow_up_days,
    )

    try:
        case_uuid = UUID(case_id_str)
    except (ValueError, AttributeError):
        logger.error("write_tasks: invalid case_id %r", case_id_str)
        return _empty_result("invalid_case_id")

    today = datetime.now(tz=timezone.utc).date()
    all_tasks: list[Task] = []

    # Step 2 — lab test tasks
    for item in recommended_tests:
        task = _build_test_task(case_uuid, item, created_by)
        if task is not None:
            all_tasks.append(task)

    # Step 3 — medication tasks
    for item in recommended_medications:
        task = _build_medication_task(case_uuid, item, today, created_by)
        if task is not None:
            all_tasks.append(task)

    # Step 4 — mandatory follow-up
    all_tasks.append(_build_followup_task(case_uuid, today, follow_up_days, created_by))

    logger.info("write_tasks: saving %d tasks for case %s", len(all_tasks), case_id_str)

    # Step 5 — persist each task independently
    task_ids: list[str] = []
    tasks_failed: int = 0
    breakdown: dict[str, int] = {"lab_tests": 0, "medications": 0, "followups": 0}
    due_dates: list = []

    for task in all_tasks:
        try:
            saved = await create_task(task)
            task_ids.append(str(saved.task_id))

            if task.task_type == "lab_test":
                breakdown["lab_tests"] += 1
            elif task.task_type == "medication":
                breakdown["medications"] += 1
            elif task.task_type == "followup":
                breakdown["followups"] += 1

            if task.due_date is not None:
                due_dates.append(task.due_date)

        except Exception:
            tasks_failed += 1
            logger.exception(
                "write_tasks: failed to save task type=%s desc=%r",
                task.task_type,
                task.description[:60],
            )

    earliest_due = str(min(due_dates)) if due_dates else ""
    latest_due = str(max(due_dates)) if due_dates else ""

    logger.info(
        "write_tasks OK | created=%d | failed=%d | breakdown=%s",
        len(task_ids),
        tasks_failed,
        breakdown,
    )

    return {
        "tasks_created": len(task_ids),
        "tasks_failed": tasks_failed,
        "task_ids": task_ids,
        "task_breakdown": breakdown,
        "earliest_due": earliest_due,
        "latest_due": latest_due,
    }


# ---------------------------------------------------------------------------
# Re-register with real implementation
# ---------------------------------------------------------------------------

from agents.tool_registry import REGISTRY, Tool  # noqa: E402

REGISTRY.register(
    Tool(
        name="task_writer",
        description="Create follow-up tasks from clinical reasoning output with due dates and priorities",
        input_schema={
            "type": "object",
            "properties": {
                "case_id":                 {"type": "string"},
                "recommended_tests":       {"type": "array"},
                "recommended_medications": {"type": "array"},
                "follow_up_days":          {"type": "integer"},
                "created_by":              {"type": "string"},
            },
            "required": ["case_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "tasks_created":  {"type": "integer"},
                "tasks_failed":   {"type": "integer"},
                "task_ids":       {"type": "array", "items": {"type": "string"}},
                "task_breakdown": {"type": "object"},
                "earliest_due":   {"type": "string"},
                "latest_due":     {"type": "string"},
            },
        },
        agent="case_manager_agent",
        async_fn=write_tasks,
    )
)

logger.debug("task_writer: real implementation registered")
