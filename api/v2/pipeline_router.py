"""
ClinIQ 2.0 — FastAPI router for the agentic pipeline (v2).

Mounts at /api/v2.  All endpoints are async and route through
ClinIQPipeline.  The singleton pipeline is initialised once at
first request to avoid paying startup cost when other endpoints
are hit first.
"""

import asyncio
import dataclasses
import io
import json
import logging
import os
import time
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from agents.pipeline import ClinIQPipeline, PipelineRequest, PipelineResponse
from agents.planner import ClinIQPlanner
from agents.tool_registry import REGISTRY
from db.timeline import write_timeline_event as _tl_write
from db.models import (
    Case,
    CaseResponse,
    CreatePatientRequest,
    Escalation,
    LabReport,
    Patient,
    Task,
    TimelineEvent,
)
from db.supabase_client import (
    TABLE_CASES,
    TABLE_LAB_REPORTS,
    TABLE_PATIENTS,
    create_patient,
    get_active_cases_for_clinic,
    get_case,
    get_case_summary_for_clinic,
    get_client,
    get_lab_reports,
    get_overdue_tasks,
    get_patient,
    get_timeline,
    get_unresolved_escalations,
    save_lab_report,
    update_lab_report_analysis,
    update_lab_report_deepdive,
    write_timeline_event,
)

logger = logging.getLogger("cliniq.api.v2")
lab_logger = logging.getLogger("cliniq.api.v2.lab_upload")

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

_PDF_CONTENT_TYPES = {"application/pdf"}
_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
_PDF_EXTENSIONS = {".pdf"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

router = APIRouter(prefix="/api/v2", tags=["ClinIQ v2"])

# ---------------------------------------------------------------------------
# Lazy singletons — created once, reused across requests
# ---------------------------------------------------------------------------

_pipeline: ClinIQPipeline | None = None
_planner: ClinIQPlanner | None = None


def _get_pipeline() -> ClinIQPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ClinIQPipeline()
        logger.info("ClinIQPipeline singleton created")
    return _pipeline


def _get_planner() -> ClinIQPlanner:
    global _planner
    if _planner is None:
        _planner = ClinIQPlanner()
        logger.info("ClinIQPlanner singleton created")
    return _planner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sse(payload: dict) -> str:
    """Format a dict as a Server-Sent Events data line."""
    return f"data: {json.dumps(payload, default=str)}\n\n"


async def _load_patient_map(patient_ids: list[str]) -> dict[str, Patient]:
    """Batch-fetch patients by ID and return a lookup dict."""
    if not patient_ids:
        return {}
    try:
        db = await get_client()
        res = await db.table(TABLE_PATIENTS).select("*").in_("patient_id", patient_ids).execute()
        return {row["patient_id"]: Patient(**row) for row in res.data}
    except Exception:
        logger.exception("_load_patient_map failed")
        return {}


def _to_case_response(case: Case, patient_map: dict[str, Patient]) -> CaseResponse:
    patient = patient_map.get(str(case.patient_id))
    return CaseResponse(
        **case.model_dump(),
        patient_name=patient.name if patient else "Unknown",
        patient_phone=patient.phone if patient else "",
    )


# ---------------------------------------------------------------------------
# GET /api/v2/health
# ---------------------------------------------------------------------------


@router.get("/health")
async def health():
    """Liveness check — also reports how many tools are registered."""
    return {
        "status": "ok",
        "version": "2.0",
        "tools_registered": len(REGISTRY.list_tools()),
    }


# ---------------------------------------------------------------------------
# POST /api/v2/analyze
# ---------------------------------------------------------------------------


@router.post(
    "/analyze",
    response_model=PipelineResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze(request: PipelineRequest) -> PipelineResponse:
    """Run the full ClinIQ 2.0 agentic pipeline and return a structured response."""
    logger.info(
        "POST /analyze | patient=%s | case=%s | type=%s",
        request.patient_id,
        request.case_id,
        request.input_type,
    )
    try:
        response = await _get_pipeline().run(request)
    except Exception as exc:
        logger.exception("POST /analyze: pipeline raised unexpectedly")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=response.error or "Pipeline failed",
        )

    # Write symptom_reported timeline event after the pipeline succeeds.
    if request.case_id and str(request.case_id).strip():
        output = response.output if hasattr(response, "output") and isinstance(response.output, dict) else {}
        diagnoses  = output.get("diagnosis_hypotheses", [])
        top_dx     = diagnoses[0] if diagnoses and isinstance(diagnoses[0], dict) else {}
        india_ctx  = output.get("india_context") or output.get("india_epi_flag")
        await _tl_write(
            case_id    = str(request.case_id),
            event_type = "symptom_reported",
            payload    = {
                "symptoms_extracted": output.get("symptoms", []),
                "top_diagnosis":      top_dx.get("diagnosis", ""),
                "top_confidence":     float(top_dx.get("confidence", 0.0)),
                "india_epi_applied":  bool(india_ctx),
            },
            agent_name = "ClinIQPipeline",
        )

    return response


# ---------------------------------------------------------------------------
# POST /api/v2/analyze/stream
# ---------------------------------------------------------------------------


@router.post("/analyze/stream")
async def analyze_stream(request: PipelineRequest) -> StreamingResponse:
    """
    SSE variant of /analyze.

    Emits stage events as the pipeline progresses:
      planning → executing (per tool) → synthesizing → complete

    For now the tool events are emitted from the plan before execution
    begins.  Real per-tool interleaved streaming arrives in a future phase.
    """
    logger.info(
        "POST /analyze/stream | patient=%s | type=%s",
        request.patient_id,
        request.input_type,
    )

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()

        async def drive():
            try:
                # -- planning stage --
                await queue.put({"stage": "planning", "message": "Analyzing symptoms..."})

                patient = await get_patient(request.patient_id)
                if patient is None:
                    await queue.put({"stage": "error", "message": "Patient not found"})
                    return

                # Derive a quick plan so we can emit per-tool events
                case_obj = None
                if request.case_id:
                    case_obj = await get_case(request.case_id)

                # Dummy case for planning preview when case not yet created
                if case_obj is None:
                    from db.models import Case as CaseModel
                    case_obj = CaseModel(
                        patient_id=request.patient_id,
                        chief_complaint=request.user_input[:255],
                    )

                try:
                    plan = await _get_planner().plan(
                        user_input=request.user_input,
                        patient=patient,
                        case=case_obj,
                        additional_context={"input_type": request.input_type},
                    )
                    tool_names = [tc.tool_name for tc in plan.tool_calls]
                except Exception:
                    tool_names = ["symptom_extractor", "clinical_reasoner"]

                # -- executing stage (one event per tool) --
                for tool_name in tool_names:
                    await queue.put({"stage": "executing", "tool": tool_name})

                # -- synthesizing stage --
                await queue.put({"stage": "synthesizing", "message": "Generating response..."})

                # -- full pipeline run --
                response = await _get_pipeline().run(request)

                await queue.put({
                    "stage": "complete",
                    "response": response.model_dump(mode="json"),
                })
            except Exception as exc:
                logger.exception("analyze_stream drive() error")
                await queue.put({"stage": "error", "message": str(exc)})
            finally:
                await queue.put(None)  # sentinel

        task = asyncio.create_task(drive())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield _sse(item)
        finally:
            task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# GET /api/v2/case/{case_id}
# ---------------------------------------------------------------------------


@router.get("/case/{case_id}")
async def get_case_detail(case_id: UUID) -> dict:
    """Return a case together with its timeline events and lab reports."""
    logger.info("GET /case/%s", case_id)
    try:
        case, timeline, lab_reports = await asyncio.gather(
            get_case(case_id),
            get_timeline(case_id),
            get_lab_reports(case_id),
        )
    except Exception as exc:
        logger.exception("GET /case/%s: DB error", case_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    return {
        "case": case.model_dump(mode="json"),
        "timeline": [e.model_dump(mode="json") for e in timeline],
        "lab_reports": [r.model_dump(mode="json") for r in lab_reports],
    }


# ---------------------------------------------------------------------------
# GET /api/v2/patient/{patient_id}/cases
# ---------------------------------------------------------------------------


@router.get("/patient/{patient_id}/cases")
async def get_patient_cases(patient_id: UUID) -> dict:
    """Return all cases for a patient ordered by created_at descending."""
    logger.info("GET /patient/%s/cases", patient_id)
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_CASES)
            .select("*")
            .eq("patient_id", str(patient_id))
            .order("created_at", desc=True)
            .execute()
        )
        cases = [Case(**row) for row in res.data]
    except Exception as exc:
        logger.exception("GET /patient/%s/cases: DB error", patient_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return {"patient_id": str(patient_id), "cases": [c.model_dump(mode="json") for c in cases]}


# ---------------------------------------------------------------------------
# POST /api/v2/patient
# ---------------------------------------------------------------------------


@router.post("/patient", response_model=Patient, status_code=status.HTTP_201_CREATED)
async def create_patient_endpoint(body: CreatePatientRequest) -> Patient:
    """Create a new patient record."""
    logger.info("POST /patient | phone=%s", body.phone)
    try:
        patient = await create_patient(body)
    except Exception as exc:
        logger.exception("POST /patient: DB error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return patient


# ---------------------------------------------------------------------------
# GET /api/v2/clinic/{clinic_id}/dashboard
# ---------------------------------------------------------------------------


@router.get("/clinic/{clinic_id}/dashboard")
async def clinic_dashboard(clinic_id: UUID) -> dict:
    """
    Doctor dashboard aggregate.

    Returns case counts, active cases enriched with patient info,
    unresolved escalations, and overdue tasks scoped to this clinic.
    """
    logger.info("GET /clinic/%s/dashboard", clinic_id)
    try:
        summary, active_cases, escalations, all_overdue = await asyncio.gather(
            get_case_summary_for_clinic(clinic_id),
            get_active_cases_for_clinic(clinic_id),
            get_unresolved_escalations(clinic_id),
            get_overdue_tasks(),
        )
    except Exception as exc:
        logger.exception("GET /clinic/%s/dashboard: DB error", clinic_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # Scope overdue tasks to this clinic's cases
    clinic_case_ids = {str(c.case_id) for c in active_cases}
    overdue_tasks = [t for t in all_overdue if str(t.case_id) in clinic_case_ids]

    # Enrich active cases with patient name + phone
    patient_ids = [str(c.patient_id) for c in active_cases]
    patient_map = await _load_patient_map(patient_ids)
    case_responses = [_to_case_response(c, patient_map) for c in active_cases]

    return {
        "summary": summary,
        "active_cases": [cr.model_dump(mode="json") for cr in case_responses],
        "escalations": [e.model_dump(mode="json") for e in escalations],
        "overdue_tasks": [t.model_dump(mode="json") for t in overdue_tasks],
    }


# ---------------------------------------------------------------------------
# POST /api/v2/admin/trigger-watch
# ---------------------------------------------------------------------------


@router.post("/admin/trigger-watch")
async def trigger_watch(
    x_admin_secret: str | None = Header(default=None),
) -> dict:
    """
    Manually trigger run_daily_watch() for testing and on-demand runs.
    Protected by X-Admin-Secret header.
    """
    admin_secret = os.environ.get("ADMIN_SECRET", "")
    if not admin_secret or x_admin_secret != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Admin-Secret header",
        )
    logger.info("POST /admin/trigger-watch: manual trigger requested")
    try:
        from workers.watch_worker import run_daily_watch  # local import — avoids circular at module load

        summary = await run_daily_watch()
        return dataclasses.asdict(summary)
    except Exception as exc:
        logger.exception("POST /admin/trigger-watch: run_daily_watch failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ===========================================================================
# Lab report upload helpers
# ===========================================================================


def _sniff_file_type(filename: str, content_type: str) -> str:
    """Return 'pdf', 'image', or 'unsupported' based on MIME type and extension."""
    import pathlib
    ext = pathlib.Path(filename or "").suffix.lower()
    if content_type in _PDF_CONTENT_TYPES or ext in _PDF_EXTENSIONS:
        return "pdf"
    if content_type in _IMAGE_CONTENT_TYPES or ext in _IMAGE_EXTENSIONS:
        return "image"
    return "unsupported"


async def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from a PDF using pdfplumber, executed in a threadpool."""
    def _do_extract() -> str:
        import pdfplumber  # type: ignore[import]
        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n".join(pages)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _do_extract)


async def _extract_image_text(file_bytes: bytes) -> str:
    """OCR an image using pytesseract + Pillow, executed in a threadpool."""
    def _do_ocr() -> str:
        import pytesseract  # type: ignore[import]
        from PIL import Image  # type: ignore[import]
        img = Image.open(io.BytesIO(file_bytes))
        return pytesseract.image_to_string(img)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _do_ocr)


async def _extract_text(file_bytes: bytes, file_type: str) -> tuple[str, str | None]:
    """
    Extract raw text from a lab report file.
    Returns (text, error_message).  text is empty string on failure.
    """
    try:
        if file_type == "pdf":
            text = await _extract_pdf_text(file_bytes)
            return text, None
        if file_type == "image":
            text = await _extract_image_text(file_bytes)
            return text, None
    except Exception as exc:
        lab_logger.exception("_extract_text failed for file_type=%s", file_type)
        return "extraction_failed", str(exc)
    return "", "unsupported_file_type"


# ===========================================================================
# POST /api/v2/lab-report/upload
# ===========================================================================


@router.post("/lab-report/upload", status_code=status.HTTP_201_CREATED)
async def upload_lab_report(
    case_id: str = Form(...),
    report_type: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    """
    Upload a PDF or image lab report, extract text, run DeepDive analysis,
    persist the report and a timeline event, and optionally trigger a
    monitoring plan for high/critical risk findings.
    """
    lab_logger.info(
        "POST /lab-report/upload | case=%s | type=%s | filename=%s | mime=%s",
        case_id, report_type, file.filename, file.content_type,
    )

    # --- file type check ---
    file_type = _sniff_file_type(file.filename or "", file.content_type or "")
    if file_type == "unsupported":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type: {file.content_type}. Upload PDF or image.",
        )

    # --- size guard (read once, reuse bytes) ---
    file_bytes = await file.read()
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 50 MB limit.",
        )

    # --- load case + patient for context ---
    try:
        case_uuid = UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid case_id")

    case = await get_case(case_uuid)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    patient = await get_patient(case.patient_id)  # type: ignore[arg-type]
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    # --- Step 1: extract text ---
    extracted_text, extract_error = await _extract_text(file_bytes, file_type)
    if extract_error and extracted_text != "extraction_failed":
        extracted_text = "extraction_failed"
    lab_logger.info("Text extraction | chars=%d | error=%s", len(extracted_text), extract_error)

    # --- Step 2: save raw LabReport ---
    try:
        raw_report = LabReport(
            case_id=case_uuid,
            report_type=report_type,  # type: ignore[arg-type]
            raw_text=extracted_text,
        )
        saved_report = await save_lab_report(raw_report)
        report_id = saved_report.report_id
    except Exception as exc:
        lab_logger.exception("save_lab_report failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # --- Step 3: run DeepDive ---
    try:
        from agents.tools.deepdive import run_deepdive  # local — avoids startup import cost

        deepdive_result = await run_deepdive({
            "report_type":      report_type,
            "raw_text":         extracted_text if extracted_text != "extraction_failed" else "",
            "patient_age":      patient.age or 30,
            "patient_sex":      patient.sex or "unknown",
            "known_conditions": patient.known_conditions or [],
        })
        if extract_error:
            deepdive_result["extraction_error"] = extract_error
    except Exception as exc:
        lab_logger.exception("run_deepdive failed for report_id=%s", report_id)
        deepdive_result = {
            "report_type": report_type, "risk_level": "low", "abnormal_count": 0,
            "primary_finding": "", "error": str(exc),
        }

    # --- Step 4: persist DeepDive output ---
    try:
        await update_lab_report_deepdive(report_id, deepdive_result)  # type: ignore[arg-type]
    except Exception:
        lab_logger.exception("update_lab_report_deepdive failed for report_id=%s", report_id)

    # --- Step 5: write timeline event ---
    timeline_event_id: str | None = None
    try:
        event = await write_timeline_event(
            case_id=case_uuid,
            event_type="lab_upload",
            title=f"{report_type} report uploaded and analyzed",
            content={
                "report_id":      str(report_id),
                "report_type":    report_type,
                "abnormal_count": deepdive_result.get("abnormal_count", 0),
                "risk_level":     deepdive_result.get("risk_level", "low"),
                "primary_finding": deepdive_result.get("primary_finding", ""),
            },
            source="patient",
        )
        timeline_event_id = str(event.event_id)
    except Exception:
        lab_logger.exception("write_timeline_event failed for case_id=%s", case_id)

    # --- Step 6: auto-trigger monitoring plan for high/critical risk ---
    monitoring_triggered = False
    risk_level: str = deepdive_result.get("risk_level", "low")
    primary_finding: str = deepdive_result.get("primary_finding", "")

    if risk_level in ("high", "critical"):
        lab_logger.info(
            "High-risk lab result (%s) — auto-triggering monitoring plan for case %s",
            risk_level, case_id,
        )
        try:
            mp_result = await REGISTRY.execute("monitoring_plan_writer", {
                "case_id":           case_id,
                "diagnosis_context": primary_finding,
                "risk_tier":         risk_level,
                "differentials":     [],
                "patient_language":  patient.language_preference,
            })
            monitoring_triggered = mp_result.get("success", False)
        except Exception:
            lab_logger.exception("Auto monitoring plan failed for case_id=%s", case_id)

    lab_logger.info(
        "upload_lab_report complete | report_id=%s | risk=%s | monitoring=%s",
        report_id, risk_level, monitoring_triggered,
    )
    return {
        "report_id":           str(report_id),
        "report_type":         report_type,
        "deep_dive":           deepdive_result,
        "timeline_event_id":   timeline_event_id,
        "monitoring_triggered": monitoring_triggered,
        "extraction_error":    extract_error,
    }


# ---------------------------------------------------------------------------
# GET /api/v2/lab-report/{report_id}
# ---------------------------------------------------------------------------


@router.get("/lab-report/{report_id}")
async def get_lab_report_detail(report_id: UUID) -> dict:
    """Return a single lab report including its full deep_dive_output."""
    lab_logger.info("GET /lab-report/%s", report_id)
    try:
        db = await get_client()
        res = (
            await db.table(TABLE_LAB_REPORTS)
            .select("*")
            .eq("report_id", str(report_id))
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        return LabReport(**res.data[0]).model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as exc:
        lab_logger.exception("GET /lab-report/%s: DB error", report_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /api/v2/case/{case_id}/lab-reports
# ---------------------------------------------------------------------------


@router.get("/case/{case_id}/lab-reports")
async def list_case_lab_reports(case_id: UUID) -> dict:
    """Return all lab reports for a case ordered by uploaded_at descending."""
    lab_logger.info("GET /case/%s/lab-reports", case_id)
    try:
        reports = await get_lab_reports(case_id)
    except Exception as exc:
        lab_logger.exception("GET /case/%s/lab-reports: DB error", case_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return {
        "case_id":  str(case_id),
        "count":    len(reports),
        "reports":  [r.model_dump(mode="json") for r in reports],
    }
