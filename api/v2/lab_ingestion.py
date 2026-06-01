"""
ClinIQ 2.0 — Lab report ingestion pipeline.

POST /api/v2/cases/{case_id}/labs/upload
  1. File-type validation (PDF / JPEG / PNG)
  2. OCR: pdfplumber for native PDFs, PyMuPDF→pytesseract for scanned PDFs,
          pytesseract directly for images
  3. Keyword-based report-type classifier (CBC / LFT / RFT / ECG / Xray / generic)
  4. Persist initial lab_reports row (raw_text + detected report_type)
  5. Route to DeepDive interpreter
  6. Update row: extracted_values, abnormal_flags, deep_dive_output
  7. Write timeline event
"""

import asyncio
import io
import logging
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from agents.tools.deepdive import run_deepdive
from db.models import LabReport
from db.supabase_client import (
    get_case,
    get_patient,
    save_lab_report,
    update_lab_report_analysis,
    write_timeline_event,
)

logger = logging.getLogger("cliniq.api.v2.lab_ingestion")

_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
_SCANNED_PDF_THRESHOLD = 100   # chars; below this pdfplumber result → try OCR fallback

router = APIRouter(prefix="/api/v2", tags=["Lab Ingestion"])

# ---------------------------------------------------------------------------
# Report-type keyword classifier
# ---------------------------------------------------------------------------

_CBC_KW = frozenset({
    "haemoglobin", "hemoglobin", "hgb", "hb\n", "hb:",
    "wbc", "tlc", "leukocyte", "leucocyte",
    "platelet", "plt", "thrombocyte",
    "rbc", "erythrocyte", "hematocrit", "haematocrit", "hct", "pcv",
    "neutrophil", "lymphocyte", "monocyte", "eosinophil", "basophil",
    "mcv", "mch", "mchc", "rdw",
    "complete blood count", "cbc", "blood count", "full blood",
    "polymorphs", "mpv",
})

_LFT_KW = frozenset({
    "bilirubin", "sgot", "sgpt",
    " alt ", "alt:", " ast ", "ast:",
    "alkaline phosphatase", "alp", "ggt", "gamma-gt",
    "albumin", "globulin", "total protein",
    "liver function", "lft", "hepatic function",
    "a/g ratio",
})

_RFT_KW = frozenset({
    "creatinine", "urea", "blood urea nitrogen", "bun",
    "uric acid", " gfr", "egfr", "kidney function",
    "rft", "renal function", "renal profile",
    "sodium", "potassium", "chloride", "bicarbonate",
    "electrolyte", "serum creatinine",
})

_ECG_KW = frozenset({
    "ecg", "ekg", "electrocardiogram", "electrocardiograph",
    "heart rate", "sinus rhythm", "atrial", "ventricular",
    "qrs complex", "p wave", "t wave", "st segment", "qt interval",
    "bundle branch", "arrhythmia", "bradycardia", "tachycardia",
    "rhythm strip", "12-lead",
})

_XRAY_KW = frozenset({
    "x-ray", "xray", "x ray", "radiograph", "chest pa",
    "pa view", "ap view", "opacity", "consolidation",
    "cardiomegaly", "pleural effusion", "infiltrate", "lung field",
    "radiology report", "radiological",
    "bone density", "fracture", "dislocation",
})

_CLASSIFIER = [
    ("CBC",  _CBC_KW),
    ("LFT",  _LFT_KW),
    ("RFT",  _RFT_KW),
    ("ECG",  _ECG_KW),
    ("Xray", _XRAY_KW),
]

# Maps classifier output → LabReport.report_type Literal
_TO_MODEL_TYPE = {
    "CBC": "CBC", "LFT": "LFT", "RFT": "RFT",
    "ECG": "ECG", "Xray": "Xray", "generic": "other",
}


def classify_report_type(text: str) -> str:
    """
    Count keyword hits per category; return the winner or 'generic'.
    Requires at least 2 hits to avoid false positives on short fragments.
    """
    lower = " " + text.lower() + " "
    scores: dict[str, int] = {
        label: sum(1 for kw in kws if kw in lower)
        for label, kws in _CLASSIFIER
    }
    best_label, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_label if best_score >= 2 else "generic"


# ---------------------------------------------------------------------------
# OCR helpers  (all CPU-bound work dispatched to a thread-pool executor)
# ---------------------------------------------------------------------------


def _pdfplumber_extract(file_bytes: bytes) -> tuple[str, float]:
    import pdfplumber  # type: ignore[import]

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
    text = "\n".join(pages)
    # Confidence proxy: more characters → higher certainty it's a selectable PDF
    confidence = min(0.95, 0.40 + len(text) / 3000.0) if text else 0.0
    return text, confidence


def _tesseract_confidence(img) -> float:
    """Average word-level confidence returned by pytesseract (0.0 – 1.0)."""
    import pytesseract  # type: ignore[import]

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    confs = [c for c in data["conf"] if isinstance(c, (int, float)) and c != -1]
    return (sum(confs) / len(confs) / 100.0) if confs else 0.0


def _ocr_image_bytes(img_bytes: bytes) -> tuple[str, float]:
    import pytesseract  # type: ignore[import]
    from PIL import Image  # type: ignore[import]

    img = Image.open(io.BytesIO(img_bytes))
    return pytesseract.image_to_string(img), _tesseract_confidence(img)


def _pdf_scanned_ocr(file_bytes: bytes) -> tuple[str, float]:
    """Rasterise every PDF page with PyMuPDF then OCR with pytesseract."""
    import fitz  # type: ignore[import]  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    parts: list[str] = []
    conf_scores: list[float] = []
    for page in doc:
        mat = fitz.Matrix(2.0, 2.0)   # 2× zoom improves OCR accuracy
        pix = page.get_pixmap(matrix=mat)
        text, conf = _ocr_image_bytes(pix.tobytes("png"))
        parts.append(text)
        conf_scores.append(conf)
    combined_text = "\n".join(parts)
    avg_conf = (sum(conf_scores) / len(conf_scores)) if conf_scores else 0.0
    return combined_text, avg_conf


async def _extract_pdf(file_bytes: bytes) -> tuple[str, float]:
    """
    Primary: pdfplumber (native text layer).
    Fallback: rasterise with PyMuPDF → pytesseract (scanned / image-only PDFs).
    """
    loop = asyncio.get_running_loop()
    native_text, native_conf = await loop.run_in_executor(
        None, _pdfplumber_extract, file_bytes
    )

    if len(native_text) >= _SCANNED_PDF_THRESHOLD:
        return native_text, native_conf

    # Sparse native text — probably scanned; try OCR fallback
    try:
        ocr_text, ocr_conf = await loop.run_in_executor(
            None, _pdf_scanned_ocr, file_bytes
        )
        if len(ocr_text) > len(native_text):
            logger.info(
                "Scanned-PDF OCR fallback used: native=%d chars → ocr=%d chars",
                len(native_text), len(ocr_text),
            )
            return ocr_text, ocr_conf
    except Exception:
        logger.exception("Scanned-PDF OCR fallback failed; keeping native result")

    return native_text, native_conf


async def _extract_image(file_bytes: bytes) -> tuple[str, float]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ocr_image_bytes, file_bytes)


async def _extract(file_bytes: bytes, file_type: str) -> tuple[str, float, str | None]:
    """
    Dispatch OCR by file type.
    Returns (raw_text, confidence_score, error_message | None).
    """
    try:
        if file_type == "pdf":
            text, conf = await _extract_pdf(file_bytes)
            return text, conf, None
        if file_type == "image":
            text, conf = await _extract_image(file_bytes)
            return text, conf, None
    except Exception as exc:
        logger.exception("OCR extraction failed for file_type=%s", file_type)
        return "", 0.0, str(exc)
    return "", 0.0, "unsupported_file_type"


# ---------------------------------------------------------------------------
# File-type sniffer
# ---------------------------------------------------------------------------


def _sniff_file_type(filename: str, content_type: str) -> str:
    """Return 'pdf', 'image', or 'unsupported'."""
    import pathlib

    ext = pathlib.Path(filename or "").suffix.lower()
    if content_type == "application/pdf" or ext == ".pdf":
        return "pdf"
    if content_type in {"image/jpeg", "image/jpg", "image/png"} or ext in {
        ".jpg", ".jpeg", ".png"
    }:
        return "image"
    return "unsupported"


# ---------------------------------------------------------------------------
# POST /api/v2/cases/{case_id}/labs/upload
# ---------------------------------------------------------------------------


@router.post(
    "/cases/{case_id}/labs/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a lab report file for a case and run DeepDive analysis",
)
async def upload_case_lab(
    case_id: UUID,
    file: UploadFile = File(...),
) -> dict:
    """
    Ingest a PDF or image lab report for a specific case.

    Returns the full structured analysis: report_type, extracted_values,
    interpretation from DeepDive, and critical_flags, all persisted to
    the lab_reports row.
    """
    # --- validate file type ---
    file_type = _sniff_file_type(file.filename or "", file.content_type or "")
    if file_type == "unsupported":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                "Upload a PDF (.pdf), JPEG (.jpg/.jpeg), or PNG (.png)."
            ),
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(file_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 50 MB limit.",
        )

    # --- load case and patient ---
    case = await get_case(case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Case not found."
        )
    patient = await get_patient(case.patient_id)  # type: ignore[arg-type]
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found."
        )

    # --- OCR extraction ---
    raw_text, confidence_score, extract_error = await _extract(file_bytes, file_type)
    logger.info(
        "OCR done | case=%s | file_type=%s | chars=%d | conf=%.2f | err=%s",
        case_id, file_type, len(raw_text), confidence_score, extract_error,
    )

    # --- classify report type ---
    classified_type = classify_report_type(raw_text) if raw_text else "generic"
    model_type = _TO_MODEL_TYPE[classified_type]
    logger.info("Classified | case=%s | type=%s", case_id, classified_type)

    # --- persist initial row (raw file reference) ---
    try:
        initial = LabReport(
            case_id=case_id,
            report_type=model_type,  # type: ignore[arg-type]
            raw_text=raw_text or None,
        )
        saved = await save_lab_report(initial)
        report_id = saved.report_id
    except Exception as exc:
        logger.exception("save_lab_report failed | case=%s", case_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )

    # --- run DeepDive ---
    try:
        deepdive_result = await run_deepdive({
            "report_type":      classified_type,
            "raw_text":         raw_text or "",
            "patient_age":      patient.age or 30,
            "patient_sex":      patient.sex or "unknown",
            "known_conditions": patient.known_conditions or [],
        })
        deepdive_result["ocr_confidence"] = round(confidence_score, 3)
        if extract_error:
            deepdive_result["extraction_error"] = extract_error
    except Exception as exc:
        logger.exception("run_deepdive failed | report_id=%s", report_id)
        deepdive_result = {
            "report_type":    classified_type,
            "risk_level":     "low",
            "abnormal_count": 0,
            "abnormal_flags": [],
            "parsed_values":  {},
            "primary_finding": "",
            "clinical_summary": "DeepDive unavailable — manual review required.",
            "ocr_confidence": round(confidence_score, 3),
            "error": str(exc),
        }

    # --- extract structured fields ---
    extracted_values: dict = deepdive_result.get("parsed_values", {})
    all_flags: list[dict] = deepdive_result.get("abnormal_flags", [])
    critical_flags: list[dict] = [
        f for f in all_flags
        if isinstance(f, dict) and f.get("severity") == "critical"
    ]

    # --- update row with full analysis ---
    try:
        await update_lab_report_analysis(
            report_id=report_id,  # type: ignore[arg-type]
            parsed_values=extracted_values,
            abnormal_flags=all_flags,
            deep_dive_output=deepdive_result,
        )
    except Exception:
        logger.exception("update_lab_report_analysis failed | report_id=%s", report_id)

    # --- timeline event ---
    timeline_event_id: str | None = None
    try:
        evt = await write_timeline_event(
            case_id=case_id,
            event_type="lab_upload",
            title=f"{classified_type} report uploaded and analyzed",
            content={
                "report_id":        str(report_id),
                "report_type":      classified_type,
                "filename":         file.filename,
                "confidence_score": round(confidence_score, 3),
                "abnormal_count":   len(all_flags),
                "critical_count":   len(critical_flags),
                "risk_level":       deepdive_result.get("risk_level", "low"),
                "primary_finding":  deepdive_result.get("primary_finding", ""),
            },
            source="patient",
        )
        timeline_event_id = str(evt.event_id)
    except Exception:
        logger.exception("write_timeline_event failed | case=%s", case_id)

    logger.info(
        "upload_case_lab complete | report_id=%s | type=%s | risk=%s | "
        "flags=%d | critical=%d | conf=%.2f",
        report_id, classified_type,
        deepdive_result.get("risk_level", "low"),
        len(all_flags), len(critical_flags), confidence_score,
    )

    return {
        "report_id":         str(report_id),
        "case_id":           str(case_id),
        "filename":          file.filename,
        "report_type":       classified_type,
        "raw_text":          raw_text,
        "confidence_score":  round(confidence_score, 3),
        "extracted_values":  extracted_values,
        "interpretation":    deepdive_result,
        "critical_flags":    critical_flags,
        "abnormal_count":    len(all_flags),
        "timeline_event_id": timeline_event_id,
        "extraction_error":  extract_error,
    }
