"""
ClinIQ 2.0 main orchestrator.

ClinIQPipeline is the single entry point for the FastAPI layer.
It runs all 6 stages in order — INTAKE → PLAN → EXECUTE → SYNTHESIZE →
PERSIST → RETURN — feeding each stage's output into the next, timing
every stage, and never letting a PERSIST failure deny the user their
clinical synthesis.
"""

import json
import logging
import os
import time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from agents.planner import ClinIQPlanner, PlanExecutionResult, ToolPlan
from db.models import (
    AgentNote,
    Case,
    Checkpoint,
    CreateCaseRequest,
    CreatePatientRequest,
    Escalation,
    MonitoringPlan,
    Patient,
    Task,
)
from db.supabase_client import (
    append_agent_note,
    create_case,
    create_escalation,
    create_monitoring_plan,
    create_patient,
    create_task,
    get_case,
    get_patient,
    update_case_risk,
    write_timeline_event,
)
from db.models import UpdateCaseRiskRequest
from backend.llm.router import llm_chat

logger = logging.getLogger("cliniq.pipeline")

# ---------------------------------------------------------------------------
# Synthesizer system prompt
# Placeholders filled with .replace() — the prompt body contains literal
# JSON in its instructions which would break str.format().
# ---------------------------------------------------------------------------

_SYNTHESIZER_PROMPT = """You are ClinIQ, an India-aware clinical AI assistant.

You have just executed a clinical analysis plan. Here are the results from each tool:

PLACEHOLDER_TOOL_RESULTS_JSON

Patient: PLACEHOLDER_PATIENT_NAME, PLACEHOLDER_PATIENT_AGEyr PLACEHOLDER_PATIENT_SEX, PLACEHOLDER_PATIENT_LOCATION
Known conditions: PLACEHOLDER_KNOWN_CONDITIONS
Chief complaint: PLACEHOLDER_CHIEF_COMPLAINT

Using the tool results above, provide a comprehensive clinical response that:
1. Summarizes key findings clearly
2. States the most likely diagnoses with confidence levels
3. Flags any abnormal lab values or critical risk factors
4. Recommends specific next steps (tests, medications, referrals)
5. Mentions India-specific context (local disease prevalence, drug availability, Jan Aushadhi alternatives if relevant)
6. Uses simple language the patient can understand for any patient-facing parts
7. Ends with a monitoring summary if a monitoring plan was created

Be direct. Be specific. Never say "consult a doctor" as the only advice — you ARE the clinical support system."""


def _render_synthesizer_prompt(
    tool_results: str,
    patient: Patient,
    case: Case,
) -> str:
    return (
        _SYNTHESIZER_PROMPT
        .replace("PLACEHOLDER_TOOL_RESULTS_JSON", tool_results)
        .replace("PLACEHOLDER_PATIENT_NAME", patient.name or "Unknown")
        .replace("PLACEHOLDER_PATIENT_AGE", str(patient.age or "unknown"))
        .replace("PLACEHOLDER_PATIENT_SEX", patient.sex or "unknown")
        .replace("PLACEHOLDER_PATIENT_LOCATION", patient.location or "India")
        .replace("PLACEHOLDER_KNOWN_CONDITIONS", ", ".join(patient.known_conditions or []) or "none")
        .replace("PLACEHOLDER_CHIEF_COMPLAINT", case.chief_complaint or "not specified")
    )


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class PipelineRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID | None = None
    case_id: UUID | None = None
    user_input: str
    input_type: Literal["text", "voice_transcript", "lab_report", "image_report"]
    report_type: str | None = None
    language: str = "en"
    clinic_id: UUID | None = None


class PipelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool
    case_id: UUID | None = None
    patient_id: UUID | None = None
    synthesis: str
    plan_reasoning: str
    tools_executed: list[str]
    risk_tier: str
    risk_flags: list[str]
    monitoring_plan_created: bool
    monitoring_plan_id: str | None
    tasks_created: int
    timeline_event_id: UUID | None
    error: str | None
    total_time_ms: int


# ---------------------------------------------------------------------------
# Persist stage result carrier (internal only)
# ---------------------------------------------------------------------------


class _PersistResult:
    def __init__(self) -> None:
        self.timeline_event_id: UUID | None = None
        self.monitoring_plan_id: str | None = None
        self.tasks_created: int = 0
        self.monitoring_plan_created: bool = False


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class ClinIQPipeline:
    """Runs the full ClinIQ 2.0 agentic pipeline end to end."""

    def __init__(self) -> None:
        self._planner = ClinIQPlanner()
        logger.info("ClinIQPipeline initialised")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, request: PipelineRequest) -> PipelineResponse:
        """Execute all 6 pipeline stages and return a structured response."""
        total_start = time.perf_counter()

        try:
            patient, case = await self._stage_intake(request)
        except Exception as exc:
            logger.exception("INTAKE stage failed")
            return self._error_response(request, str(exc), total_start)

        try:
            plan = await self._stage_plan(request, patient, case)
        except Exception as exc:
            logger.exception("PLAN stage failed")
            return self._error_response(request, str(exc), total_start, case)

        try:
            execution = await self._stage_execute(plan, patient, case)
        except Exception as exc:
            logger.exception("EXECUTE stage failed")
            return self._error_response(request, str(exc), total_start, case)

        try:
            synthesis = await self._stage_synthesize(request, patient, case, execution)
        except Exception as exc:
            logger.exception("SYNTHESIZE stage failed")
            synthesis = "Clinical analysis complete. Please review tool outputs for details."

        # PERSIST: failures are logged but never crash the pipeline
        persist = await self._stage_persist(request, case, execution, synthesis)

        total_ms = int((time.perf_counter() - total_start) * 1000)
        logger.info("Pipeline complete | total_ms=%d | success=True", total_ms)
        return self._build_response(request, case, execution, synthesis, persist, total_ms)

    # ------------------------------------------------------------------
    # Stage 1 — INTAKE
    # ------------------------------------------------------------------

    async def _stage_intake(
        self, request: PipelineRequest
    ) -> tuple[Patient, Case]:
        t = time.perf_counter()
        logger.info("Stage INTAKE starting | patient_id=%s", request.patient_id)

        if request.patient_id is not None:
            patient = await get_patient(request.patient_id)
            if patient is None:
                raise ValueError(f"Patient {request.patient_id} not found")
        else:
            # First-time user: no patient_id supplied — auto-create an anonymous record.
            patient = await create_patient(CreatePatientRequest(
                name="ClinIQ Patient",
                phone=f"anon_{int(time.time() * 1000)}",
            ))
            logger.info("Auto-created patient %s", patient.patient_id)

        if request.case_id is not None:
            case = await get_case(request.case_id)
            if case is None:
                raise ValueError(f"Case {request.case_id} not found")
        else:
            case = await create_case(
                CreateCaseRequest(
                    patient_id=patient.patient_id,  # type: ignore[arg-type]
                    chief_complaint=request.user_input[:255],
                    clinic_id=request.clinic_id,
                )
            )
            logger.info("Created new case %s", case.case_id)

        logger.info("Stage INTAKE complete | ms=%d", _ms(t))
        return patient, case

    # ------------------------------------------------------------------
    # Stage 2 — PLAN
    # ------------------------------------------------------------------

    async def _stage_plan(
        self,
        request: PipelineRequest,
        patient: Patient,
        case: Case,
    ) -> ToolPlan:
        t = time.perf_counter()
        logger.info("Stage PLAN starting | case_id=%s", case.case_id)

        plan = await self._planner.plan(
            user_input=request.user_input,
            patient=patient,
            case=case,
            additional_context={
                "input_type": request.input_type,
                "language": request.language,
                "report_type": request.report_type,
            },
        )

        logger.info(
            "Stage PLAN complete | tools=%s | ms=%d",
            [tc.tool_name for tc in plan.tool_calls],
            _ms(t),
        )
        return plan

    # ------------------------------------------------------------------
    # Stage 3 — EXECUTE
    # ------------------------------------------------------------------

    async def _stage_execute(
        self,
        plan: ToolPlan,
        patient: Patient,
        case: Case,
    ) -> PlanExecutionResult:
        t = time.perf_counter()
        logger.info("Stage EXECUTE starting | %d tools", len(plan.tool_calls))

        result = await self._planner.execute_plan(plan, patient, case)

        logger.info(
            "Stage EXECUTE complete | success=%s | ms=%d",
            result.all_succeeded,
            _ms(t),
        )
        return result

    # ------------------------------------------------------------------
    # Stage 4 — SYNTHESIZE
    # ------------------------------------------------------------------

    async def _stage_synthesize(
        self,
        request: PipelineRequest,
        patient: Patient,
        case: Case,
        execution: PlanExecutionResult,
    ) -> str:
        t = time.perf_counter()
        logger.info("Stage SYNTHESIZE starting")

        system_prompt = _render_synthesizer_prompt(
            tool_results=json.dumps(execution.combined_output, indent=2, default=str),
            patient=patient,
            case=case,
        )
        synthesis = await llm_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.user_input},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        logger.info("Stage SYNTHESIZE complete | chars=%d | ms=%d", len(synthesis), _ms(t))
        return synthesis

    # ------------------------------------------------------------------
    # Stage 5 — PERSIST
    # ------------------------------------------------------------------

    async def _stage_persist(
        self,
        request: PipelineRequest,
        case: Case,
        execution: PlanExecutionResult,
        synthesis: str,
    ) -> _PersistResult:
        t = time.perf_counter()
        logger.info("Stage PERSIST starting | case_id=%s", case.case_id)
        pr = _PersistResult()

        risk_tier, risk_flags = _extract_risk(execution)
        tools_executed = [r.tool_name for r in execution.results]

        if risk_tier in ("high", "critical"):
            await self._escalate_if_critical(case, risk_tier, risk_flags)

        await self._persist_risk(case, risk_tier, risk_flags)
        pr.timeline_event_id = await self._persist_timeline(
            case, request, execution, synthesis, risk_tier
        )
        pr.monitoring_plan_created, pr.monitoring_plan_id = await self._persist_monitoring(
            case, execution
        )
        pr.tasks_created = await self._persist_tasks(case, execution)
        await self._persist_agent_note(
            case, tools_executed, risk_tier, pr.monitoring_plan_created
        )

        logger.info("Stage PERSIST complete | ms=%d", _ms(t))
        return pr

    async def _escalate_if_critical(
        self, case: Case, risk_tier: str, risk_flags: list[str]
    ) -> None:
        severity = "emergency" if risk_tier == "critical" else "alert"
        try:
            escalation = Escalation(
                case_id=case.case_id,  # type: ignore[arg-type]
                patient_id=case.patient_id,
                severity=severity,
                trigger_reason=f"Pipeline analysis flagged risk_tier={risk_tier}",
                trigger_evidence={"risk_tier": risk_tier, "risk_flags": risk_flags},
            )
            await create_escalation(escalation)
            logger.info(
                "PERSIST: escalation created | case=%s | severity=%s",
                case.case_id, severity,
            )
        except Exception:
            logger.exception("PERSIST: create_escalation failed for case_id=%s", case.case_id)

    async def _persist_risk(self, case: Case, risk_tier: str, risk_flags: list[str]) -> None:
        try:
            await update_case_risk(
                case.case_id,  # type: ignore[arg-type]
                UpdateCaseRiskRequest(risk_tier=risk_tier, risk_flags=risk_flags),
            )
        except Exception:
            logger.exception("PERSIST: update_case_risk failed for case_id=%s", case.case_id)

    async def _persist_timeline(
        self,
        case: Case,
        request: PipelineRequest,
        execution: PlanExecutionResult,
        synthesis: str,
        risk_tier: str,
    ) -> UUID | None:
        try:
            event = await write_timeline_event(
                case_id=case.case_id,  # type: ignore[arg-type]
                event_type="agent_synthesis",
                title=request.user_input[:80],
                content={
                    "plan_reasoning": execution.plan.reasoning,
                    "tools_executed": [r.tool_name for r in execution.results],
                    "synthesis_preview": synthesis[:200],
                    "risk_tier": risk_tier,
                    "combined_tool_outputs": execution.combined_output,
                },
                source="agent",
            )
            return event.event_id
        except Exception:
            logger.exception("PERSIST: write_timeline_event failed for case_id=%s", case.case_id)
            return None

    async def _persist_monitoring(
        self,
        case: Case,
        execution: PlanExecutionResult,
    ) -> tuple[bool, str | None]:
        mp_output = execution.combined_output.get("monitoring_plan_writer", {})
        raw_checkpoints = mp_output.get("checkpoints", [])
        if not raw_checkpoints:
            return False, None
        try:
            checkpoints = [Checkpoint(**cp) for cp in raw_checkpoints]
            plan = MonitoringPlan(
                case_id=case.case_id,  # type: ignore[arg-type]
                diagnosis_context=mp_output.get("diagnosis_context", ""),
                checkpoints=checkpoints,
            )
            saved = await create_monitoring_plan(plan)
            return True, str(saved.plan_id)
        except Exception:
            logger.exception("PERSIST: create_monitoring_plan failed for case_id=%s", case.case_id)
            return False, None

    async def _persist_tasks(self, case: Case, execution: PlanExecutionResult) -> int:
        tw_output = execution.combined_output.get("task_writer", {})
        raw_tasks = tw_output.get("tasks", [])
        if not raw_tasks:
            return 0
        created = 0
        for raw in raw_tasks:
            try:
                task = Task(
                    case_id=case.case_id,  # type: ignore[arg-type]
                    **{k: v for k, v in raw.items() if k != "case_id"},
                )
                await create_task(task)
                created += 1
            except Exception:
                logger.exception("PERSIST: create_task failed for case_id=%s", case.case_id)
        return created

    async def _persist_agent_note(
        self,
        case: Case,
        tools_executed: list[str],
        risk_tier: str,
        monitoring_created: bool,
    ) -> None:
        try:
            from datetime import datetime

            note = AgentNote(
                agent_name="pipeline_orchestrator",
                note=(
                    f"Pipeline ran {len(tools_executed)} tools. "
                    f"Risk: {risk_tier}. "
                    f"Monitoring: {monitoring_created}"
                ),
                timestamp=datetime.utcnow(),
            )
            await append_agent_note(case.case_id, note)  # type: ignore[arg-type]
        except Exception:
            logger.exception("PERSIST: append_agent_note failed for case_id=%s", case.case_id)

    # ------------------------------------------------------------------
    # Stage 6 — RETURN
    # ------------------------------------------------------------------

    def _build_response(
        self,
        request: PipelineRequest,
        case: Case,
        execution: PlanExecutionResult,
        synthesis: str,
        persist: _PersistResult,
        total_ms: int,
    ) -> PipelineResponse:
        risk_tier, risk_flags = _extract_risk(execution)
        return PipelineResponse(
            success=True,
            case_id=case.case_id,      # type: ignore[arg-type]
            patient_id=case.patient_id,  # type: ignore[arg-type]
            synthesis=synthesis,
            plan_reasoning=execution.plan.reasoning,
            tools_executed=[r.tool_name for r in execution.results],
            risk_tier=risk_tier,
            risk_flags=risk_flags,
            monitoring_plan_created=persist.monitoring_plan_created,
            monitoring_plan_id=persist.monitoring_plan_id,
            tasks_created=persist.tasks_created,
            timeline_event_id=persist.timeline_event_id,
            error=None,
            total_time_ms=total_ms,
        )

    def _error_response(
        self,
        request: PipelineRequest,
        error: str,
        start: float,
        case: Case | None = None,
    ) -> PipelineResponse:
        return PipelineResponse(
            success=False,
            case_id=case.case_id if case and case.case_id else request.patient_id,  # type: ignore[arg-type]
            patient_id=request.patient_id,
            synthesis="",
            plan_reasoning="",
            tools_executed=[],
            risk_tier="low",
            risk_flags=[],
            monitoring_plan_created=False,
            monitoring_plan_id=None,
            tasks_created=0,
            timeline_event_id=None,
            error=error,
            total_time_ms=_ms(start),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ms(start: float) -> int:
    """Elapsed milliseconds since a perf_counter snapshot."""
    return int((time.perf_counter() - start) * 1000)


def _extract_risk(execution: PlanExecutionResult) -> tuple[str, list[str]]:
    """Pull risk_tier and risk_flags from clinical_reasoner output, with safe defaults."""
    cr = execution.combined_output.get("clinical_reasoner", {})
    tier = cr.get("risk_tier", "low")
    flags = cr.get("risk_flags", [])
    # india_epidemiology_reranker may augment flags
    er = execution.combined_output.get("india_epidemiology_reranker", {})
    india_flags = er.get("india_specific_flags", [])
    merged_flags = list({*flags, *india_flags})
    return tier, merged_flags
