-- =============================================================================
-- ClinIQ 2.0 — Core missing tables
-- Safe to run on any DB; all statements use IF NOT EXISTS.
--
-- IMPORTANT: The column names here MUST match what the application code
-- reads and writes. Do NOT use the simplified DDL from ad-hoc notes —
-- use this file as the single source of truth.
--
-- Cases PK is 'case_id' (uuid), confirmed from 001_cliniq_schema.sql.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- timeline_events
--
-- Application writes:  case_id, event_type, title, content, source, event_date
-- Application reads:   event_id (PK), event_type, content, event_date,
--                      title, created_at
--
-- DO NOT rename columns — the app references them by exact name.
-- ---------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_timeline_events_case_id
    ON timeline_events(case_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_date
    ON timeline_events(event_date);
CREATE INDEX IF NOT EXISTS idx_timeline_events_event_type
    ON timeline_events(event_type);

ALTER TABLE timeline_events DISABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- agent_activity
--
-- Not present in 001_cliniq_schema.sql — this is the only genuinely
-- missing table in the core pipeline.
--
-- Application writes:  case_id, agent_name, action, finding, created_at
-- Application reads:   id (PK), case_id, agent_name, action, finding,
--                      created_at
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_activity (
    id          uuid         DEFAULT gen_random_uuid() PRIMARY KEY,
    case_id     uuid         REFERENCES cases(case_id) ON DELETE CASCADE,
    agent_name  text         NOT NULL,
    action      text         NOT NULL,
    finding     text,
    created_at  timestamptz  DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_activity_case_created
    ON agent_activity(case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS agent_activity_created
    ON agent_activity(created_at DESC);

ALTER TABLE agent_activity DISABLE ROW LEVEL SECURITY;
