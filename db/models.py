from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Nested / value-object models (no table, embedded in JSONB columns)
# ---------------------------------------------------------------------------

# Risk condition thresholds stored inside a Checkpoint
class CheckpointRiskConditions(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    escalate_if: list[str]
    watch_if: list[str]
    resolve_if: list[str]


# Agent evaluation result stored inside a Checkpoint
class CheckpointAgentEvaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_change: str | None = None
    action_taken: str | None = None
    summary: str | None = None


# Single monitoring checkpoint stored in monitoring_plans.checkpoints[]
class Checkpoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_offset: int
    scheduled_date: date
    questions: list[str]
    risk_conditions: CheckpointRiskConditions
    status: Literal["pending", "sent", "responded", "overdue"] = "pending"
    whatsapp_message_id: str | None = None
    patient_response: str | None = None
    response_received_at: datetime | None = None
    agent_evaluation: CheckpointAgentEvaluation | None = None


# Single diagnosis hypothesis stored in cases.diagnosis_hypotheses[]
class DiagnosisHypothesis(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    diagnosis: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str]


# Single agent note stored in cases.agent_notes[]
class AgentNote(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_name: str
    note: str
    timestamp: datetime
    metadata: dict = {}


# Single abnormal lab marker stored in lab_reports.abnormal_flags[]
class AbnormalFlag(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    marker: str
    value: str
    reference_range: str
    severity: Literal["mild", "moderate", "critical"]
    interpretation: str


# ---------------------------------------------------------------------------
# Table-level models (one per Supabase table)
# ---------------------------------------------------------------------------

# Maps to the clinics table
class Clinic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_id: UUID | None = None
    name: str
    doctor_name: str | None = None
    phone: str | None = None
    city: str | None = None
    created_at: datetime | None = None


# Maps to the patients table
class Patient(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID | None = None
    clinic_id: UUID | None = None
    name: str
    age: int | None = None
    sex: Literal["male", "female", "other"] | None = None
    phone: str
    language_preference: str = "en"
    location: str | None = None
    known_conditions: list[str] = []
    current_medications: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


# Maps to the cases table
class Case(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: UUID | None = None
    patient_id: UUID
    clinic_id: UUID | None = None
    status: Literal["active", "monitoring", "resolved", "escalated"] = "active"
    chief_complaint: str | None = None
    diagnosis_hypotheses: list[DiagnosisHypothesis] = []
    risk_tier: Literal["low", "moderate", "high", "critical"] = "low"
    risk_flags: list[str] = []
    agent_notes: list[AgentNote] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


# Maps to the timeline_events table
class TimelineEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: UUID | None = None
    case_id: UUID
    event_type: Literal[
        "symptom_report",
        "lab_upload",
        "agent_synthesis",
        "whatsapp_checkin",
        "medication_start",
        "escalation",
        "resolution",
    ]
    event_date: datetime
    title: str
    content: dict = {}
    source: Literal["patient", "doctor", "agent"]
    created_at: datetime | None = None


# Maps to the lab_reports table
class LabReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: UUID | None = None
    case_id: UUID
    report_type: Literal["CBC", "LFT", "RFT", "ECG", "Xray", "prescription", "other"]
    raw_text: str | None = None
    parsed_values: dict = {}
    abnormal_flags: list[AbnormalFlag] = []
    deep_dive_output: dict = {}
    uploaded_at: datetime | None = None


# Maps to the monitoring_plans table
class MonitoringPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: UUID | None = None
    case_id: UUID
    status: Literal["active", "completed", "cancelled"] = "active"
    diagnosis_context: str | None = None
    checkpoints: list[Checkpoint] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


# Maps to the tasks table
class Task(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: UUID | None = None
    case_id: UUID
    task_type: Literal["followup", "lab_test", "medication", "monitoring", "referral"]
    description: str
    due_date: date | None = None
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    status: Literal["pending", "sent", "completed", "overdue"] = "pending"
    reminder_channel: Literal["whatsapp", "dashboard"] = "whatsapp"
    created_by: str | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


# Maps to the whatsapp_messages table
class WhatsappMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: UUID | None = None
    case_id: UUID
    patient_id: UUID
    direction: Literal["inbound", "outbound"]
    content: str
    language_detected: str | None = None
    checkpoint_day_offset: int | None = None
    processed: bool = False
    agent_evaluation: dict = {}
    sent_at: datetime | None = None
    received_at: datetime | None = None
    created_at: datetime | None = None


# Maps to the escalations table
class Escalation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    escalation_id: UUID | None = None
    case_id: UUID
    patient_id: UUID
    severity: Literal["watch", "alert", "emergency"]
    trigger_reason: str
    trigger_evidence: dict = {}
    checkpoint_context: dict = {}
    doctor_notified: bool = False
    doctor_notified_at: datetime | None = None
    resolved: bool = False
    resolved_at: datetime | None = None
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Request / response models for FastAPI endpoints
# ---------------------------------------------------------------------------

# Request body for POST /patients
class CreatePatientRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    phone: str
    age: int | None = None
    sex: Literal["male", "female", "other"] | None = None
    language_preference: str = "en"
    location: str | None = None
    known_conditions: list[str] = []
    current_medications: list[str] = []
    clinic_id: UUID | None = None


# Request body for POST /cases
class CreateCaseRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID
    chief_complaint: str
    clinic_id: UUID | None = None


# Request body for PATCH /cases/{case_id}/risk
class UpdateCaseRiskRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_tier: Literal["low", "moderate", "high", "critical"]
    risk_flags: list[str]


# Case response enriched with patient name and phone for frontend convenience
class CaseResponse(Case):
    model_config = ConfigDict(from_attributes=True)

    patient_name: str
    patient_phone: str


# Realtime escalation alert payload sent to the doctor dashboard
class EscalationAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    escalation_id: UUID
    case_id: UUID
    patient_name: str
    patient_phone: str
    severity: Literal["watch", "alert", "emergency"]
    trigger_reason: str
    created_at: datetime
