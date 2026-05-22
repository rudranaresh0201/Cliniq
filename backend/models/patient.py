import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PatientProfile(BaseModel):
    id: str
    age: Optional[int] = None
    gender: Optional[str] = None
    existing_conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class HealthEpisode(BaseModel):
    id: Optional[str] = None
    patient_id: str
    query: str
    triage: str
    conditions: list[str] = Field(default_factory=list)
    response_summary: Optional[str] = None
    timestamp: Optional[datetime] = None


class AnalyzeRequestV2(BaseModel):
    """Extends the v1 request with an optional user_id for longitudinal tracking."""
    query: str = Field(..., min_length=3, max_length=1000)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = None
    medications: list[str] = Field(default_factory=list)
    existing_conditions: list[str] = Field(default_factory=list)
    user_id: Optional[str] = Field(None, description="Patient user_id for history tracking")
    state: str = "Maharashtra"


class CreatePatientRequest(BaseModel):
    user_id: str
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = None
    existing_conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)


class UpdateMedicationsRequest(BaseModel):
    medications: list[str]
