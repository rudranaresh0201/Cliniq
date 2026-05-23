import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional

from backend.multimodal.report_parser import parse_report
from backend.multimodal.report_agent import interpret_report
from backend.db.database import save_episode

logger = logging.getLogger("cliniq")
router = APIRouter(prefix="/api/reports", tags=["reports"])

ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "text/plain",
    "text/csv",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload_report(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    age: Optional[int] = Form(None),
    gender: Optional[str] = Form(None),
    existing_conditions: Optional[str] = Form(None),
    medications: Optional[str] = Form(None),
):
    """
    Accept a PDF, image, or text lab report, parse values, interpret abnormal results,
    and optionally save to patient history if user_id is provided.
    """
    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES:
        # Some browsers send empty or generic MIME for .txt — fall back to text/plain
        if file.filename and file.filename.lower().endswith(('.txt', '.csv')):
            content_type = 'text/plain'
        else:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type '{content_type}'. Upload a PDF, image, or text file.",
            )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Parse the report
    parsed = parse_report(file_bytes, content_type)

    # Build patient context from form fields
    patient_context = {
        "age": age,
        "gender": gender,
        "existing_conditions": [c.strip() for c in (existing_conditions or "").split(",") if c.strip()],
        "medications": [m.strip() for m in (medications or "").split(",") if m.strip()],
    }

    # LLM interpretation — pass full parsed dict so agent can branch on report type
    interpretation = await interpret_report(parsed, patient_context)

    # Optionally persist episode
    if user_id and (parsed["abnormal_count"] > 0 or parsed.get("is_imaging_report") or parsed.get("is_prescription")):
        try:
            save_episode(
                user_id=user_id,
                query=f"{parsed.get('report_type', 'report').upper()} upload — {parsed['abnormal_count']} abnormal value(s)",
                response={"patient_summary": interpretation.get("interpretation", "")},
                triage=_urgency_to_triage(interpretation.get("overall_urgency", "routine")),
                conditions_flagged=[
                    e["test"] for e in interpretation.get("abnormal_explanations", [])
                ],
            )
        except Exception as e:
            logger.warning(f"Could not save lab episode: {e}")

    return {
        "filename": file.filename,
        "content_type": content_type,
        "parsed": {
            "report_type": parsed.get("report_type", "general_medical"),
            "values": parsed["values"],
            "abnormal_count": parsed["abnormal_count"],
            "critical_count": parsed["critical_count"],
            "abnormal_values": parsed.get("abnormal_values", {}),
            "is_imaging_report": parsed.get("is_imaging_report", False),
            "is_prescription": parsed.get("is_prescription", False),
        },
        "interpretation": interpretation,
    }


def _urgency_to_triage(urgency: str) -> str:
    return {"immediate": "EMERGENCY", "urgent": "URGENT", "routine": "ROUTINE"}.get(urgency, "ROUTINE")
