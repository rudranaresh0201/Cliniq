import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import logging
from fastapi import APIRouter, HTTPException

from backend.db.database import (
    create_patient,
    get_patient,
    get_patient_history,
    get_patient_profile,
    update_medications,
)
from backend.agents.timeline import analyze_timeline
from backend.models.patient import CreatePatientRequest, UpdateMedicationsRequest

logger = logging.getLogger("cliniq")
router = APIRouter(prefix="/api/patient", tags=["patient"])


@router.post("/create")
async def create_patient_route(body: CreatePatientRequest):
    try:
        row = create_patient(
            user_id=body.user_id,
            age=body.age,
            gender=body.gender,
            existing_conditions=body.existing_conditions,
            medications=body.medications,
        )
        return {"status": "ok", "patient": row}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}")
async def get_patient_route(user_id: str):
    profile = get_patient(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Patient not found")
    return profile


@router.get("/{user_id}/history")
async def get_history_route(user_id: str, limit: int = 20):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be 1–100")
    history = get_patient_history(user_id, limit=limit)
    return {"user_id": user_id, "episodes": history, "count": len(history)}


@router.get("/{user_id}/timeline")
async def get_timeline_route(user_id: str):
    history = get_patient_history(user_id, limit=20)
    if not history:
        return {
            "patterns_detected": [],
            "trend": "insufficient_data",
            "proactive_recommendation": "No history yet",
            "urgency": "routine",
        }
    analysis = await analyze_timeline(history)
    return analysis


@router.post("/{user_id}/medications")
async def update_medications_route(user_id: str, body: UpdateMedicationsRequest):
    try:
        row = update_medications(user_id, body.medications)
        return {"status": "ok", "updated": row}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
