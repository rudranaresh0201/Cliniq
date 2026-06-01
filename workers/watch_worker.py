"""
ClinIQ 2.0 Autonomous Watch Worker — runs daily at 8am IST, monitors all
active patient checkpoints, processes inbound WhatsApp replies, triggers
escalations without human intervention.

The worker is the heartbeat of the ClinIQ monitoring loop:
  Phase 1: Send today's due checkpoint messages to patients
  Phase 2: Evaluate any unprocessed inbound replies for escalation
  Phase 3: Send reminders for overdue tasks
  Phase 4: Return a structured run summary

APScheduler prevents concurrent runs (max_instances=1).
All phases are fault-isolated — one patient failing never stops the others.
"""

import dataclasses
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import UUID

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from groq import AsyncGroq

from db.models import Case, Checkpoint, MonitoringPlan, Task, WhatsappMessage
from db.timeline import write_timeline_event as _tl_write
from db.supabase_client import (
    TABLE_TASKS,
    get_active_monitoring_plans,
    get_case,
    get_client,
    get_due_checkpoints_today,
    get_overdue_tasks,
    get_patient,
    get_unprocessed_inbound_messages,
    mark_message_processed,
    mark_task_complete,
    save_whatsapp_message,
    update_checkpoint,
)

logger = logging.getLogger("cliniq.workers.watch_worker")

# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------

WATCH_WORKER_HOUR: int = int(os.getenv("WATCH_WORKER_HOUR", "8"))
WATCH_WORKER_MINUTE: int = int(os.getenv("WATCH_WORKER_MINUTE", "0"))
WORKER_TIMEZONE: str = os.getenv("WORKER_TIMEZONE", "Asia/Kolkata")
WHATSAPP_MODE: str = os.getenv("WHATSAPP_MODE", "log")
DOCTOR_PHONE: str = os.getenv("DOCTOR_PHONE", "")
DOCTOR_TELEGRAM_CHAT_ID: str = os.getenv("DOCTOR_TELEGRAM_CHAT_ID", "")
ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "")

_GROQ_MODEL = "llama-3.3-70b-versatile"

# ---------------------------------------------------------------------------
# WatchRunSummary — returned by run_daily_watch()
# ---------------------------------------------------------------------------


@dataclass
class WatchRunSummary:
    run_date: date
    checkpoints_due: int = 0
    checkpoints_sent: int = 0
    checkpoints_failed: int = 0
    messages_processed: int = 0
    escalations_triggered: int = 0
    tasks_reminded: int = 0
    overdue_tasks_found: int = 0
    total_duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal result carriers
# ---------------------------------------------------------------------------


@dataclass
class _InboundResult:
    success: bool
    escalation_triggered: bool = False
    cross_escalation_triggered: bool = False


# ---------------------------------------------------------------------------
# APScheduler — module-level singleton
# ---------------------------------------------------------------------------

scheduler = AsyncIOScheduler(timezone=WORKER_TIMEZONE)

# ---------------------------------------------------------------------------
# Groq client — lazily initialised
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


# ===========================================================================
# MAIN JOB — run_daily_watch
# ===========================================================================


async def run_daily_watch() -> WatchRunSummary:
    """
    Main scheduled job.  Runs all four watch phases and returns a summary.
    Each phase is isolated — failures in one never abort the others.
    """
    job_start = time.perf_counter()
    summary = WatchRunSummary(run_date=datetime.now(tz=timezone.utc).date())
    logger.info("=== ClinIQ Watch Worker starting | %s ===", summary.run_date)

    # ------------------------------------------------------------------
    # Phase 1 — send due checkpoint messages
    # ------------------------------------------------------------------
    phase_start = time.perf_counter()
    logger.info("Phase 1: processing due checkpoints")
    try:
        due_pairs = await get_due_checkpoints_today()
        summary.checkpoints_due = len(due_pairs)
        logger.info("Phase 1: %d checkpoints due today", summary.checkpoints_due)

        for plan, checkpoint in due_pairs:
            try:
                sent = await send_checkpoint_message(plan, checkpoint)
                if sent:
                    summary.checkpoints_sent += 1
                else:
                    summary.checkpoints_failed += 1
            except Exception as exc:
                summary.checkpoints_failed += 1
                msg = f"Checkpoint send failed for plan {plan.plan_id}: {exc}"
                summary.errors.append(msg)
                logger.exception("Phase 1: %s", msg)

    except Exception as exc:
        msg = f"Phase 1 failed entirely: {exc}"
        summary.errors.append(msg)
        logger.exception(msg)

    logger.info(
        "Phase 1 done | sent=%d failed=%d | %.1fs",
        summary.checkpoints_sent,
        summary.checkpoints_failed,
        time.perf_counter() - phase_start,
    )

    # ------------------------------------------------------------------
    # Phase 2 — process inbound messages
    # ------------------------------------------------------------------
    phase_start = time.perf_counter()
    logger.info("Phase 2: processing inbound messages")
    try:
        inbound = await get_unprocessed_inbound_messages()
        logger.info("Phase 2: %d unprocessed messages", len(inbound))

        for message in inbound:
            try:
                result = await process_inbound_message(message)
                if result.success:
                    summary.messages_processed += 1
                if result.escalation_triggered:
                    summary.escalations_triggered += 1
                if result.cross_escalation_triggered:
                    summary.escalations_triggered += 1
            except Exception as exc:
                msg = f"Inbound message {message.message_id} failed: {exc}"
                summary.errors.append(msg)
                logger.exception("Phase 2: %s", msg)

    except Exception as exc:
        msg = f"Phase 2 failed entirely: {exc}"
        summary.errors.append(msg)
        logger.exception(msg)

    logger.info(
        "Phase 2 done | processed=%d escalations=%d | %.1fs",
        summary.messages_processed,
        summary.escalations_triggered,
        time.perf_counter() - phase_start,
    )

    # ------------------------------------------------------------------
    # Phase 3 — overdue task reminders
    # ------------------------------------------------------------------
    phase_start = time.perf_counter()
    logger.info("Phase 3: sending overdue task reminders")
    try:
        overdue = await get_overdue_tasks()
        summary.overdue_tasks_found = len(overdue)
        logger.info("Phase 3: %d overdue tasks", summary.overdue_tasks_found)

        for task in overdue:
            try:
                reminded = await send_task_reminder(task)
                if reminded:
                    summary.tasks_reminded += 1
            except Exception as exc:
                msg = f"Task reminder failed for task {task.task_id}: {exc}"
                summary.errors.append(msg)
                logger.exception("Phase 3: %s", msg)

    except Exception as exc:
        msg = f"Phase 3 failed entirely: {exc}"
        summary.errors.append(msg)
        logger.exception(msg)

    logger.info(
        "Phase 3 done | reminded=%d | %.1fs",
        summary.tasks_reminded,
        time.perf_counter() - phase_start,
    )

    # ------------------------------------------------------------------
    # Phase 4 — finalise summary
    # ------------------------------------------------------------------
    summary.total_duration_seconds = round(time.perf_counter() - job_start, 2)
    logger.info(
        "=== Watch Worker complete | %s | duration=%.1fs | errors=%d ===",
        summary.run_date,
        summary.total_duration_seconds,
        len(summary.errors),
    )
    return summary


# ===========================================================================
# Phase 1 helper — send checkpoint message
# ===========================================================================


async def send_checkpoint_message(
    plan: MonitoringPlan,
    checkpoint: Checkpoint,
) -> bool:
    """
    Compose and deliver a checkpoint WhatsApp message to the patient.
    Saves the outbound message to Supabase and marks the checkpoint 'sent'.
    Returns True on success.
    """
    try:
        # Step 1 — resolve patient
        case = await get_case(plan.case_id)  # type: ignore[arg-type]
        if case is None:
            logger.error("send_checkpoint_message: case %s not found", plan.case_id)
            return False
        patient = await get_patient(case.patient_id)  # type: ignore[arg-type]
        if patient is None:
            logger.error("send_checkpoint_message: patient %s not found", case.patient_id)
            return False

        # Step 2 — compose message
        composed = await compose_checkpoint_message(
            patient_name=patient.name,
            day_offset=checkpoint.day_offset,
            questions=checkpoint.questions,
            diagnosis_context=plan.diagnosis_context or "",
            language=patient.language_preference,
        )

        # Step 3 — send
        message_id = await send_whatsapp_message(patient.phone, composed)
        if message_id is None:
            logger.warning(
                "send_checkpoint_message: delivery failed for patient %s", patient.patient_id
            )
            return False

        # Step 4 — save outbound message
        outbound = WhatsappMessage(
            case_id=plan.case_id,  # type: ignore[arg-type]
            patient_id=case.patient_id,  # type: ignore[arg-type]
            direction="outbound",
            content=composed,
            checkpoint_day_offset=checkpoint.day_offset,
            sent_at=datetime.now(tz=timezone.utc),
            processed=True,
        )
        saved_msg = await save_whatsapp_message(outbound)

        # Step 5 — mark checkpoint sent
        await update_checkpoint(
            plan_id=plan.plan_id,  # type: ignore[arg-type]
            day_offset=checkpoint.day_offset,
            status="sent",
            whatsapp_message_id=str(saved_msg.message_id),
        )

        logger.info(
            "Checkpoint sent | plan=%s day=%d patient=%s",
            plan.plan_id,
            checkpoint.day_offset,
            patient.name,
        )

        # Write timeline event after checkpoint is successfully sent.
        await _tl_write(
            case_id    = str(plan.case_id),
            event_type = "checkpoint_sent",
            payload    = {
                "checkpoint_number": checkpoint.day_offset,
                "checkpoint_day":    checkpoint.day_offset,
                "questions_sent":    len(checkpoint.questions),
            },
            agent_name = "WatchWorker",
        )

        return True

    except Exception:
        logger.exception(
            "send_checkpoint_message failed | plan=%s day=%d",
            plan.plan_id,
            checkpoint.day_offset,
        )
        return False


# ===========================================================================
# Checkpoint message composer
# ===========================================================================

_COMPOSE_PROMPT = """You are ClinIQ, a caring medical assistant sending \
a follow-up WhatsApp message to a patient in India.

Compose a short, warm WhatsApp message that:
1. Greets the patient by name
2. Reminds them you are checking on their health
3. Asks the checkpoint questions naturally \
(not as a numbered list — make it conversational)
4. Ends with reassurance

Rules:
- Maximum 200 words
- Use simple language, no medical jargon
- If language is 'hi' or 'hinglish': write in Hinglish (Hindi + English mix) that is readable on WhatsApp
- If language is 'en': write in simple English
- Do NOT use bullet points or numbering
- Sound human and caring, not robotic
- Add one relevant health tip at the end (hydration, rest, medication timing)

Patient name: PLACEHOLDER_PATIENT_NAME
Day of monitoring: Day PLACEHOLDER_DAY_OFFSET
Context: PLACEHOLDER_DIAGNOSIS_CONTEXT
Questions to ask naturally: PLACEHOLDER_QUESTIONS
Language: PLACEHOLDER_LANGUAGE

Return ONLY the message text, no quotes, no explanation."""


async def compose_checkpoint_message(
    patient_name: str,
    day_offset: int,
    questions: list[str],
    diagnosis_context: str,
    language: str,
) -> str:
    """
    Use Groq to compose a warm, conversational WhatsApp message.
    Falls back to a plain template if Groq is unavailable.
    """
    prompt = (
        _COMPOSE_PROMPT
        .replace("PLACEHOLDER_PATIENT_NAME", patient_name)
        .replace("PLACEHOLDER_DAY_OFFSET", str(day_offset))
        .replace("PLACEHOLDER_DIAGNOSIS_CONTEXT", diagnosis_context or "general monitoring")
        .replace("PLACEHOLDER_QUESTIONS", json.dumps(questions, ensure_ascii=False))
        .replace("PLACEHOLDER_LANGUAGE", language)
    )

    try:
        response = await _get_groq().chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Compose the WhatsApp message now."},
            ],
            temperature=0.4,
            max_tokens=300,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("compose_checkpoint_message: Groq failed — using fallback")

    # Fallback — plain but functional
    qs = "\n".join(f"- {q}" for q in questions)
    return (
        f"Namaste {patient_name}! ClinIQ follow-up check (Day {day_offset}):\n\n"
        f"{qs}\n\n"
        f"Please reply with how you are feeling. "
        f"Drink plenty of water and get enough rest. Take care! 🙏"
    )


# ===========================================================================
# Phase 2 helper — process inbound message
# ===========================================================================


async def process_inbound_message(message: WhatsappMessage) -> _InboundResult:
    """
    Evaluate an inbound WhatsApp reply against its checkpoint criteria.
    Marks the message processed and triggers escalation if warranted.
    Returns _InboundResult(success, escalation_triggered).
    """
    from agents.tools.escalation_evaluator import evaluate_escalation  # local import avoids circular

    try:
        # Step 1 — load case and find matching plan + checkpoint
        case = await get_case(message.case_id)  # type: ignore[arg-type]
        if case is None:
            logger.error("process_inbound_message: case %s not found", message.case_id)
            return _InboundResult(success=False)

        checkpoint_dict: dict = {}
        plan_id_str: str | None = None

        all_plans = await get_active_monitoring_plans()
        for plan in all_plans:
            if str(plan.case_id) == str(message.case_id):
                plan_id_str = str(plan.plan_id) if plan.plan_id else None
                for cp in plan.checkpoints:
                    if cp.day_offset == message.checkpoint_day_offset:
                        checkpoint_dict = cp.model_dump(mode="json")
                        break
                break

        if not checkpoint_dict:
            logger.warning(
                "process_inbound_message: no matching checkpoint found for "
                "case=%s day_offset=%s — evaluating with empty criteria",
                message.case_id,
                message.checkpoint_day_offset,
            )

        # Step 2 — call escalation evaluator
        result = await evaluate_escalation({
            "case_id":          str(message.case_id),
            "patient_response": message.content,
            "checkpoint":       checkpoint_dict,
            "case_history": {
                "chief_complaint":       case.chief_complaint,
                "diagnosis_hypotheses":  [h.model_dump(mode="json") for h in case.diagnosis_hypotheses],
                "risk_tier":             case.risk_tier,
                "risk_flags":            case.risk_flags,
                "agent_notes":           [n.model_dump(mode="json") for n in case.agent_notes],
            },
            "plan_id":    plan_id_str,
            "patient_id": str(case.patient_id),
        })

        # Step 3 — mark processed
        await mark_message_processed(
            message_id=message.message_id,  # type: ignore[arg-type]
            agent_evaluation=result,
        )

        escalated = bool(result.get("should_escalate", False))

        # Write timeline event after reply is processed.
        await _tl_write(
            case_id    = str(message.case_id),
            event_type = "checkpoint_answered",
            payload    = {
                "checkpoint_number":    checkpoint_dict.get("day_offset", 0),
                "response_summary":     str(result.get("clinical_assessment", ""))[:200],
                "escalation_evaluated": True,
                "escalation_triggered": escalated,
            },
            agent_name = "WatchWorker",
        )

        # Step 4 — notify doctor if escalated
        if escalated:
            logger.warning(
                "ESCALATION | case=%s severity=%s reason=%s",
                message.case_id,
                result.get("severity"),
                result.get("reason"),
            )
            await notify_doctor(case, result, message)

        logger.info(
            "process_inbound_message OK | case=%s escalated=%s method=%s",
            message.case_id,
            escalated,
            result.get("evaluation_method"),
        )

        # Step 5 — cross-report lab analysis after each checkpoint reply.
        # Runs only when the case has ≥2 lab reports; never crashes the main flow.
        cross_escalated = False
        try:
            from agents.tools.deepdive.cross_report_analyzer import cross_analyze
            from db.supabase_client import get_lab_reports

            existing_labs = await get_lab_reports(message.case_id)  # type: ignore[arg-type]
            if len(existing_labs) >= 2:
                logger.info(
                    "Cross-report analysis triggered | case=%s | reports=%d",
                    message.case_id, len(existing_labs),
                )
                cross_result = await cross_analyze(message.case_id)  # type: ignore[arg-type]
                if cross_result.escalation_required:
                    cross_escalated = True
                    logger.warning(
                        "CROSS-ANALYSIS ESCALATION | case=%s | reason=%s",
                        message.case_id,
                        cross_result.escalation_reason,
                    )
                    await _notify_cross_escalation(case, cross_result)
        except Exception as cross_exc:
            logger.exception(
                "Cross-report analysis failed | case=%s: %s",
                message.case_id, cross_exc,
            )

        return _InboundResult(
            success=True,
            escalation_triggered=escalated,
            cross_escalation_triggered=cross_escalated,
        )

    except Exception:
        logger.exception(
            "process_inbound_message failed | message_id=%s", message.message_id
        )
        return _InboundResult(success=False)


# ===========================================================================
# Phase 3 helper — send task reminder
# ===========================================================================


async def send_task_reminder(task: Task) -> bool:
    """
    Send a WhatsApp reminder for an overdue task and mark it 'sent'.
    Returns True on success.
    """
    try:
        case = await get_case(task.case_id)  # type: ignore[arg-type]
        if case is None:
            logger.error("send_task_reminder: case %s not found", task.case_id)
            return False
        patient = await get_patient(case.patient_id)  # type: ignore[arg-type]
        if patient is None:
            logger.error("send_task_reminder: patient %s not found", case.patient_id)
            return False

        name = patient.name
        if task.task_type == "lab_test":
            reminder = (
                f"Namaste {name}! ClinIQ reminder: {task.description}. "
                f"Please get this done today if possible. Health first! 🙏"
            )
        elif task.task_type == "medication":
            reminder = (
                f"Namaste {name}! Medication reminder: {task.description}. "
                f"Please take your medicine on time. Stay healthy! 💊"
            )
        else:
            reminder = (
                f"Namaste {name}! ClinIQ reminder: {task.description}. Take care! 🙏"
            )

        sent = await send_whatsapp_message(patient.phone, reminder)
        if sent is None:
            return False

        # Mark task as sent (no dedicated helper — direct update)
        try:
            db = await get_client()
            await (
                db.table(TABLE_TASKS)
                .update({"status": "sent"})
                .eq("task_id", str(task.task_id))
                .execute()
            )
        except Exception:
            logger.exception("send_task_reminder: could not update task status for %s", task.task_id)

        logger.info("Task reminder sent | task=%s patient=%s", task.task_id, name)
        return True

    except Exception:
        logger.exception("send_task_reminder failed | task=%s", task.task_id)
        return False


# ===========================================================================
# WhatsApp / Telegram message dispatch
# ===========================================================================


async def _send_telegram(bot_token: str, chat_id: str, text: str) -> str | None:
    """Low-level Telegram sendMessage call. Returns message_id string or None."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text})
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("result", {}).get("message_id", ""))
    except Exception:
        logger.exception("_send_telegram failed | chat_id=%s", chat_id)
        return None


async def send_whatsapp_message(phone: str, message: str) -> str | None:
    """
    Dispatch a message to the patient.

    Modes controlled by WHATSAPP_MODE env var:
      log             — development: log only, return synthetic ID
      telegram        — route via Telegram using TELEGRAM_CHAT_MAP
      whatsapp_cloud  — Meta WhatsApp Cloud API
    """
    mode = os.getenv("WHATSAPP_MODE", "log")

    if mode == "log":
        ts = str(int(datetime.now(tz=timezone.utc).timestamp()))
        logger.info("[WHATSAPP LOG] To: %s", phone)
        logger.info("Message: %s", message)
        return f"logged_{ts}"

    if mode == "telegram":
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not bot_token:
            logger.error("send_whatsapp_message: TELEGRAM_BOT_TOKEN not set")
            return None
        raw_map = os.getenv("TELEGRAM_CHAT_MAP", "{}")
        try:
            chat_map: dict = json.loads(raw_map)
        except json.JSONDecodeError:
            logger.error("send_whatsapp_message: TELEGRAM_CHAT_MAP is not valid JSON")
            return None
        chat_id = chat_map.get(phone)
        if not chat_id:
            logger.warning("send_whatsapp_message: no Telegram chat_id mapped for %s", phone)
            return None
        return await _send_telegram(bot_token, str(chat_id), message)

    if mode == "whatsapp_cloud":
        token = os.getenv("WHATSAPP_CLOUD_TOKEN", "")
        phone_id = os.getenv("WHATSAPP_PHONE_ID", "")
        if not token or not phone_id:
            logger.error("send_whatsapp_message: WHATSAPP_CLOUD_TOKEN or WHATSAPP_PHONE_ID not set")
            return None
        url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": phone,
                        "type": "text",
                        "text": {"body": message},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("messages", [{}])[0].get("id")
        except Exception:
            logger.exception("send_whatsapp_message: WhatsApp Cloud API failed for %s", phone)
            return None

    logger.error("send_whatsapp_message: unknown WHATSAPP_MODE=%s", mode)
    return None


# ===========================================================================
# Doctor notification
# ===========================================================================


async def notify_doctor(
    case: Case,
    escalation_result: dict,
    message: WhatsappMessage,
) -> None:
    """Send an escalation alert to the doctor via Telegram and/or WhatsApp."""
    severity = escalation_result.get("severity", "watch")
    prefix = {
        "emergency": "🚨 EMERGENCY ALERT",
        "alert":     "⚠️ PATIENT ALERT",
    }.get(severity, "👁️ WATCH NOTICE")

    doctor_message = (
        f"{prefix} — ClinIQ Autonomous Monitor\n\n"
        f"Case: {case.chief_complaint}\n"
        f"Risk: {severity.upper()}\n"
        f"Reason: {escalation_result.get('reason', '')}\n\n"
        f'Patient response: "{message.content}"\n\n'
        f"Clinical assessment:\n{escalation_result.get('clinical_assessment', '')}\n\n"
        f"Recommended action:\n{escalation_result.get('recommended_action', '')}\n\n"
        f"Login to ClinIQ dashboard to review full case."
    )

    if DOCTOR_TELEGRAM_CHAT_ID:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if bot_token:
            await _send_telegram(bot_token, DOCTOR_TELEGRAM_CHAT_ID, doctor_message)
            logger.info("Doctor Telegram notification sent | severity=%s", severity)
        else:
            logger.warning("notify_doctor: TELEGRAM_BOT_TOKEN not set — Telegram skipped")

    if DOCTOR_PHONE:
        await send_whatsapp_message(DOCTOR_PHONE, doctor_message)
        logger.info("Doctor WhatsApp notification sent | severity=%s", severity)

    if not DOCTOR_TELEGRAM_CHAT_ID and not DOCTOR_PHONE:
        logger.warning(
            "notify_doctor: neither DOCTOR_TELEGRAM_CHAT_ID nor DOCTOR_PHONE configured"
        )


async def _notify_cross_escalation(case: Case, cross_result) -> None:
    """
    Notify the doctor of a cross-report lab analysis escalation.
    Mirrors notify_doctor() but uses the CrossAnalysisResult rather than a
    WhatsApp reply as the trigger evidence.
    """
    # Determine highest severity across detected patterns
    severity = "alert"
    for p in cross_result.patterns_detected:
        if p.severity == "emergency":
            severity = "emergency"
            break

    prefix = {"emergency": "🚨 EMERGENCY ALERT", "alert": "⚠️ LAB PATTERN ALERT"}.get(
        severity, "👁️ WATCH NOTICE"
    )

    doctor_message = (
        f"{prefix} — ClinIQ Cross-Report Lab Analysis\n\n"
        f"Case: {case.chief_complaint or 'unknown'}\n"
        f"Risk: {severity.upper()}\n"
        f"Pattern(s): {cross_result.escalation_reason}\n\n"
        f"Clinical analysis:\n{cross_result.groq_synthesis}\n\n"
        f"Reports analysed: {cross_result.reports_analyzed}\n"
        f"Login to ClinIQ dashboard to review full lab history."
    )

    if DOCTOR_TELEGRAM_CHAT_ID:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if bot_token:
            await _send_telegram(bot_token, DOCTOR_TELEGRAM_CHAT_ID, doctor_message)
            logger.info("Cross-analysis Telegram alert sent | severity=%s", severity)
        else:
            logger.warning("_notify_cross_escalation: TELEGRAM_BOT_TOKEN not set")

    if DOCTOR_PHONE:
        await send_whatsapp_message(DOCTOR_PHONE, doctor_message)
        logger.info("Cross-analysis WhatsApp alert sent | severity=%s", severity)

    if not DOCTOR_TELEGRAM_CHAT_ID and not DOCTOR_PHONE:
        logger.warning(
            "_notify_cross_escalation: no doctor contact configured — alert not sent"
        )


# ===========================================================================
# Scheduler lifecycle
# ===========================================================================


def start_watch_worker() -> None:
    """Register the daily job and start the APScheduler."""
    scheduler.add_job(
        run_daily_watch,
        trigger=CronTrigger(
            hour=WATCH_WORKER_HOUR,
            minute=WATCH_WORKER_MINUTE,
            timezone=WORKER_TIMEZONE,
        ),
        id="daily_watch",
        name="ClinIQ Daily Patient Watch",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(
        "Watch worker started | runs daily at %02d:%02d %s",
        WATCH_WORKER_HOUR,
        WATCH_WORKER_MINUTE,
        WORKER_TIMEZONE,
    )


def stop_watch_worker() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Watch worker stopped")


# ===========================================================================
# FastAPI lifecycle hooks
# ===========================================================================


async def on_startup() -> None:
    start_watch_worker()
    logger.info("ClinIQ Watch Worker initialized")


async def on_shutdown() -> None:
    stop_watch_worker()
    logger.info("ClinIQ Watch Worker stopped")
