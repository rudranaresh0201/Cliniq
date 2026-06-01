-- =============================================================================
-- STEP 1 — Extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- STEP 2 — updated_at trigger function
-- =============================================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- STEP 3 — Tables
-- =============================================================================

-- clinics (no foreign key dependencies)
CREATE TABLE IF NOT EXISTS clinics (
  clinic_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text        NOT NULL,
  doctor_name text,
  phone       text,
  city        text,
  created_at  timestamptz DEFAULT now()
);

-- patients (depends on: clinics)
CREATE TABLE IF NOT EXISTS patients (
  patient_id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id            uuid        REFERENCES clinics(clinic_id) ON DELETE SET NULL,
  name                 text        NOT NULL,
  age                  integer,
  sex                  text        CHECK (sex IN ('male', 'female', 'other')),
  phone                text        UNIQUE NOT NULL,
  language_preference  text        DEFAULT 'en',
  location             text,
  known_conditions     text[],
  current_medications  text[],
  created_at           timestamptz DEFAULT now(),
  updated_at           timestamptz DEFAULT now()
);

-- cases (depends on: patients, clinics)
CREATE TABLE IF NOT EXISTS cases (
  case_id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id            uuid        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  clinic_id             uuid        REFERENCES clinics(clinic_id) ON DELETE SET NULL,
  status                text        DEFAULT 'active' CHECK (status IN ('active', 'monitoring', 'resolved', 'escalated')),
  chief_complaint       text,
  diagnosis_hypotheses  jsonb       DEFAULT '[]',
  risk_tier             text        DEFAULT 'low' CHECK (risk_tier IN ('low', 'moderate', 'high', 'critical')),
  risk_flags            text[]      DEFAULT '{}',
  agent_notes           jsonb       DEFAULT '[]',
  created_at            timestamptz DEFAULT now(),
  updated_at            timestamptz DEFAULT now()
);

-- timeline_events (depends on: cases)
CREATE TABLE IF NOT EXISTS timeline_events (
  event_id    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id     uuid        NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  event_type  text        CHECK (event_type IN (
                            'symptom_report', 'lab_upload', 'agent_synthesis',
                            'whatsapp_checkin', 'medication_start', 'escalation', 'resolution'
                          )),
  event_date  timestamptz DEFAULT now(),
  title       text        NOT NULL,
  content     jsonb       DEFAULT '{}',
  source      text        CHECK (source IN ('patient', 'doctor', 'agent')),
  created_at  timestamptz DEFAULT now()
);

-- lab_reports (depends on: cases)
CREATE TABLE IF NOT EXISTS lab_reports (
  report_id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id           uuid        NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  report_type       text        CHECK (report_type IN ('CBC', 'LFT', 'RFT', 'Xray', 'prescription', 'other')),
  raw_text          text,
  parsed_values     jsonb       DEFAULT '{}',
  abnormal_flags    jsonb       DEFAULT '[]',
  deep_dive_output  jsonb       DEFAULT '{}',
  uploaded_at       timestamptz DEFAULT now()
);

-- monitoring_plans (depends on: cases)
--
-- Each element of the checkpoints jsonb array has this shape:
-- {
--   "day_offset": <integer>,
--   "scheduled_date": "<YYYY-MM-DD>",
--   "questions": ["<string>", ...],
--   "risk_conditions": {
--     "escalate_if": ["<string>", ...],
--     "watch_if":    ["<string>", ...],
--     "resolve_if":  ["<string>", ...]
--   },
--   "status": "pending" | "sent" | "responded" | "overdue",
--   "whatsapp_message_id": "<string>" | null,
--   "patient_response": "<string>" | null,
--   "response_received_at": "<timestamp string>" | null,
--   "agent_evaluation": {
--     "risk_change":  "<string>" | null,
--     "action_taken": "<string>" | null,
--     "summary":      "<string>" | null
--   } | null
-- }
CREATE TABLE IF NOT EXISTS monitoring_plans (
  plan_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id            uuid        NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  status             text        DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
  diagnosis_context  text,
  checkpoints        jsonb       DEFAULT '[]',
  created_at         timestamptz DEFAULT now(),
  updated_at         timestamptz DEFAULT now()
);

-- tasks (depends on: cases)
CREATE TABLE IF NOT EXISTS tasks (
  task_id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id           uuid        NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  task_type         text        CHECK (task_type IN ('followup', 'lab_test', 'medication', 'monitoring', 'referral')),
  description       text        NOT NULL,
  due_date          date,
  priority          text        DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
  status            text        DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'completed', 'overdue')),
  reminder_channel  text        DEFAULT 'whatsapp' CHECK (reminder_channel IN ('whatsapp', 'dashboard')),
  created_by        text,
  completed_at      timestamptz,
  created_at        timestamptz DEFAULT now()
);

-- whatsapp_messages (depends on: cases, patients)
CREATE TABLE IF NOT EXISTS whatsapp_messages (
  message_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id               uuid        NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  patient_id            uuid        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  direction             text        CHECK (direction IN ('inbound', 'outbound')),
  content               text        NOT NULL,
  language_detected     text,
  checkpoint_day_offset integer,
  processed             boolean     DEFAULT false,
  agent_evaluation      jsonb       DEFAULT '{}',
  sent_at               timestamptz,
  received_at           timestamptz,
  created_at            timestamptz DEFAULT now()
);

-- escalations (depends on: cases, patients)
CREATE TABLE IF NOT EXISTS escalations (
  escalation_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id             uuid        NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  patient_id          uuid        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  severity            text        CHECK (severity IN ('watch', 'alert', 'emergency')),
  trigger_reason      text        NOT NULL,
  trigger_evidence    jsonb       DEFAULT '{}',
  checkpoint_context  jsonb       DEFAULT '{}',
  doctor_notified     boolean     DEFAULT false,
  doctor_notified_at  timestamptz,
  resolved            boolean     DEFAULT false,
  resolved_at         timestamptz,
  created_at          timestamptz DEFAULT now()
);

-- =============================================================================
-- STEP 4 — Attach updated_at trigger to tables with updated_at column
-- =============================================================================

CREATE TRIGGER set_updated_at_patients
  BEFORE UPDATE ON patients
  FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_cases
  BEFORE UPDATE ON cases
  FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_monitoring_plans
  BEFORE UPDATE ON monitoring_plans
  FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- =============================================================================
-- STEP 5 — Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_cases_patient_id              ON cases(patient_id);
CREATE INDEX IF NOT EXISTS idx_cases_status                  ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_risk_tier               ON cases(risk_tier);

CREATE INDEX IF NOT EXISTS idx_timeline_events_case_id       ON timeline_events(case_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_date    ON timeline_events(event_date);

CREATE INDEX IF NOT EXISTS idx_lab_reports_case_id           ON lab_reports(case_id);

CREATE INDEX IF NOT EXISTS idx_monitoring_plans_case_id      ON monitoring_plans(case_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_plans_status       ON monitoring_plans(status);

CREATE INDEX IF NOT EXISTS idx_tasks_case_id                 ON tasks(case_id);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date                ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_status                  ON tasks(status);

CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_case_id     ON whatsapp_messages(case_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_patient_id  ON whatsapp_messages(patient_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_processed   ON whatsapp_messages(processed);

CREATE INDEX IF NOT EXISTS idx_escalations_case_id           ON escalations(case_id);
CREATE INDEX IF NOT EXISTS idx_escalations_severity          ON escalations(severity);
CREATE INDEX IF NOT EXISTS idx_escalations_resolved          ON escalations(resolved);

-- =============================================================================
-- STEP 6 — Row Level Security
-- =============================================================================

ALTER TABLE clinics            ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients           ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases              ENABLE ROW LEVEL SECURITY;
ALTER TABLE timeline_events    ENABLE ROW LEVEL SECURITY;
ALTER TABLE lab_reports        ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring_plans   ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks              ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_messages  ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalations        ENABLE ROW LEVEL SECURITY;

-- Permissive bypass policies (replace with proper auth policies later)
CREATE POLICY "service_role bypass" ON clinics           FOR ALL USING (true);
CREATE POLICY "service_role bypass" ON patients          FOR ALL USING (true);
CREATE POLICY "service_role bypass" ON cases             FOR ALL USING (true);
CREATE POLICY "service_role bypass" ON timeline_events   FOR ALL USING (true);
CREATE POLICY "service_role bypass" ON lab_reports       FOR ALL USING (true);
CREATE POLICY "service_role bypass" ON monitoring_plans  FOR ALL USING (true);
CREATE POLICY "service_role bypass" ON tasks             FOR ALL USING (true);
CREATE POLICY "service_role bypass" ON whatsapp_messages FOR ALL USING (true);
CREATE POLICY "service_role bypass" ON escalations       FOR ALL USING (true);

-- =============================================================================
-- STEP 7 — Realtime
-- =============================================================================

ALTER PUBLICATION supabase_realtime ADD TABLE cases, escalations;
