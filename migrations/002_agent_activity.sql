-- =============================================================================
-- Migration 002 — agent_activity table
--
-- Run this once in the Supabase SQL editor.
-- The FK references cases(case_id), NOT cases(id) — the PK column is case_id.
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_activity (
    id          UUID         DEFAULT gen_random_uuid() PRIMARY KEY,
    case_id     UUID         REFERENCES cases(case_id) ON DELETE CASCADE,
    agent_name  TEXT         NOT NULL,
    action      TEXT         NOT NULL,
    finding     TEXT,
    created_at  TIMESTAMPTZ  DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_activity_case_created
    ON agent_activity(case_id, created_at DESC);

CREATE INDEX IF NOT EXISTS agent_activity_created
    ON agent_activity(created_at DESC);

ALTER TABLE agent_activity DISABLE ROW LEVEL SECURITY;
