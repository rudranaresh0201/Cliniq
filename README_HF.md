---
title: ClinIQ Backend
emoji: 🏥
colorFrom: green
colorTo: teal
sdk: docker
pinned: false
---

# ClinIQ Backend API

Medical intelligence backend powered by PubMed + Groq AI.

## Endpoints

- `POST /api/analyze` — symptom analysis
- `POST /api/analyze/v2` — with longitudinal patient tracking
- `GET /api/analyze/stream` — SSE streaming pipeline
- `POST /api/reports/upload` — lab report interpretation
- `GET /api/patient/{id}/history` — patient history
- `GET /api/patient/{id}/timeline` — AI timeline analysis
- `GET /api/health` — health check

## Environment Variables

Set these in your HF Space secrets:

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq LLM API key |
| `SUPABASE_URL` | No | Patient history database |
| `SUPABASE_KEY` | No | Supabase service role key |
| `GEMINI_API_KEY` | No | Fallback LLM provider |
| `OPENROUTER_API_KEY` | No | Fallback LLM provider |
