<div align="center">

# ClinIQ
### Agentic Medical Intelligence Platform

**India-aware clinical AI that turns symptoms into grounded differential diagnoses — powered by real PubMed evidence, OpenFDA drug data, and a multi-stage agentic pipeline.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Live Demo](https://cliniq-frontend.vercel.app) · [API Docs](https://cliniq-backend.onrender.com/docs) · [Report Bug](https://github.com/rudranaresh0201/Cliniq/issues)

</div>

---

> **Disclaimer:** ClinIQ is a clinical decision-support tool. It is **not** a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider.

---

## What Is ClinIQ?

ClinIQ is a production-grade agentic AI system that takes a patient's symptoms, age, medications, and geographic context and runs a **9-stage pipeline** to produce:

- Differential diagnoses grounded in PubMed literature
- Drug interaction and safety checks via OpenFDA
- India-specific epidemiology adjustments (seasonal + state-level outbreaks)
- Lab report deep-dives (CBC, LFT, RFT, imaging, prescriptions)
- Longitudinal patient risk stratification and monitoring plans
- Hallucination detection via faithfulness scoring

Everything streams to the frontend in real time over SSE — so users watch the agent think, not wait for a spinner.

---

## Pipeline Architecture

```
Patient Input  (symptoms · age · medications · state)
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  Stage 1 │ Safety Check        Emergency red-flag    │
│          │                     detection             │
├─────────────────────────────────────────────────────┤
│  Stage 2 │ Cache Lookup        PubMedBERT vector     │
│          │                     similarity (ChromaDB) │
├─────────────────────────────────────────────────────┤
│  Stage 3 │ Clinical Reasoning  First-principles      │
│          │                     differential          │
├─────────────────────────────────────────────────────┤
│  Stage 4 │ Classify + Plan     Query type + tool     │
│          │                     plan generation       │
├─────────────────────────────────────────────────────┤
│  Stage 5 │ Fetch → Evaluate    ┌── PubMed search     │
│          │ Loop (≤ 3 iters)   ├── OpenFDA check      │
│          │                     └── Sufficiency eval  │
├─────────────────────────────────────────────────────┤
│  Stage 6 │ Synthesis           India-aware answer    │
├─────────────────────────────────────────────────────┤
│  Stage 7 │ Faithfulness Check  Hallucination score   │
├─────────────────────────────────────────────────────┤
│  Stage 8 │ Contradiction Check Cross-claim validation│
├─────────────────────────────────────────────────────┤
│  Stage 9 │ Persist             Timeline · monitoring │
│          │ (non-fatal)         plans · tasks         │
└─────────────────────────────────────────────────────┘
      │
      ▼
  SSE Stream → React Frontend (live per-stage events)
```

---

## Key Features

### Clinical Intelligence
| Feature | Description |
|---|---|
| **Multi-stage agentic pipeline** | 9 discrete stages with automatic evidence retry loops |
| **India-aware reranking** | Adjusts differential probabilities based on state + season (monsoon dengue vs winter flu) |
| **Evidence-grounded synthesis** | Every claim traced to a specific PubMed abstract |
| **Faithfulness scoring** | Post-synthesis hallucination detection — flags unsupported claims |
| **Contradiction detection** | Cross-validates claim consistency within the generated answer |
| **Emergency red flags** | Detects MI, stroke, sepsis, and other emergencies _before_ any LLM call |

### Lab Report DeepDive
| Feature | Description |
|---|---|
| **PDF ingestion** | PyMuPDF + pdfplumber with pytesseract OCR fallback |
| **Auto report typing** | Detects CBC · LFT · RFT · X-Ray/MRI/CT · ECG · prescription |
| **Specialist interpreters** | Dedicated interpreter per report type with abnormal value flagging |
| **Patient-facing summaries** | Plain English explanations with follow-up recommendations |

### Patient Management
| Feature | Description |
|---|---|
| **Longitudinal profiles** | Full episode history in Supabase (PostgreSQL) |
| **Timeline analysis** | Automatic pattern detection after 3+ consultations |
| **Risk stratification** | Low / Medium / High / Critical with escalation triggers |
| **Doctor console** | Timeline view, monitoring checkpoints, open tasks |

### LLM Architecture
| Provider | Role |
|---|---|
| Groq `llama-3.3-70b-versatile` | Primary — fast, free tier |
| Google Gemini `gemini-1.5-flash` | Fallback on rate limit |
| OpenRouter (configurable) | Second fallback |

Automatic provider switching with zero downtime.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python · FastAPI · Pydantic v2 |
| **LLM** | Groq · Google Gemini · OpenRouter |
| **Medical retrieval** | PubMed API · OpenFDA API |
| **Embeddings** | PubMedBERT (`pritamdeka/PubMedBERT-mnli-snli-scinli-scitail-mednli-stsb`) |
| **Vector store** | ChromaDB |
| **Database** | Supabase (PostgreSQL) |
| **PDF parsing** | PyMuPDF · pdfplumber · pytesseract |
| **Scheduling** | APScheduler |
| **Frontend** | React · TypeScript · Vite · Tailwind CSS |
| **Deployment** | Docker · Render (backend) · Vercel (frontend) · GitHub Actions |

---

## Project Structure

```
ClinIQ/
├── backend/
│   ├── agents/           # classifier, planner, synthesizer, evaluator,
│   │                     # faithfulness, contradiction, timeline
│   ├── india/            # epidemiology reranker, outbreak monitor
│   ├── llm/              # Groq → Gemini → OpenRouter fallback router
│   ├── memory/           # RAG cache (ChromaDB + PubMedBERT)
│   ├── multimodal/       # lab report parser + interpreter
│   ├── retrieval/        # PubMed, OpenFDA, hybrid search
│   ├── safety/           # red-flag emergency detector
│   └── main.py           # FastAPI app + SSE streaming pipeline
├── agents/
│   ├── pipeline.py       # ClinIQPipeline v2 (9-stage orchestrator)
│   ├── planner.py        # LLM-driven tool plan generator
│   └── tools/            # clinical_reasoner, india_reranker,
│                         # monitoring_plan_writer, escalation_evaluator,
│                         # symptom_extractor, pubmed_search, openfda_check,
│                         # deepdive/ (CBC, LFT, RFT interpreters)
├── api/v2/               # lab ingestion + pipeline router
├── db/
│   ├── supabase_client.py
│   ├── models.py         # Patient, Case, Task, MonitoringPlan, Escalation
│   └── timeline.py
├── frontend/
│   ├── src/
│   │   ├── components/   # SymptomForm, ConditionCard, RedFlags,
│   │   │                 # DrugSafety, IndiaContext, StreamingProgress
│   │   ├── app/          # patient home, deepdive, timeline, doctor console
│   │   └── hooks/        # useAnalyze, useAnalyzeStream (SSE)
│   └── vite.config.ts
├── migrations/           # Supabase SQL migrations
├── workers/              # APScheduler watch worker
├── config.py             # Centralized config + model settings
└── Dockerfile
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Supabase](https://supabase.com) account (free tier works)
- [Groq API key](https://console.groq.com) (free)

### 1. Clone & configure

```bash
git clone https://github.com/rudranaresh0201/Cliniq
cd Cliniq
cp .env.example .env
# Fill in your keys — see Environment Variables below
```

### 2. Backend

```bash
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend

```bash
cd frontend
cp .env.example .env
# Set VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

### 4. Database

Run migrations in order inside the Supabase SQL editor:

```sql
-- Run in order:
migrations/001_core_tables.sql
migrations/002_agent_activity.sql
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Primary LLM — free at [console.groq.com](https://console.groq.com) |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase anon/service key |
| `GEMINI_API_KEY` | Optional | Gemini fallback LLM |
| `OPENROUTER_API_KEY` | Optional | OpenRouter fallback LLM |
| `OPENROUTER_MODEL` | Optional | Default: `meta-llama/llama-3.3-70b-instruct` |
| `ADMIN_KEY` | Optional | Protects `/api/evaluation/run` |
| `SIMILARITY_THRESHOLD` | Optional | RAG cache hit threshold (default: `0.85`) |
| `MAX_RETRY_LOOPS` | Optional | Evidence fetch retry limit (default: `3`) |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/analyze` | Synchronous clinical analysis |
| `POST` | `/api/analyze/v2` | Analysis with patient history tracking |
| `GET` | `/api/analyze/stream` | SSE streaming analysis |
| `GET` | `/api/cache/stats` | RAG cache statistics |
| `GET` | `/api/evaluation/run` | Run evaluation suite (admin) |
| `POST` | `/api/v2/lab/ingest` | Upload and parse a lab report PDF |

### Example Request

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "severe chest pain radiating to left arm, sweating, 55yr male",
    "age": 55,
    "gender": "male",
    "medications": ["metformin", "amlodipine"],
    "existing_conditions": ["type 2 diabetes", "hypertension"],
    "state": "Maharashtra"
  }'
```

### SSE Stream Events

| Event | Payload |
|---|---|
| `safety_check` | `{status}` |
| `cache_hit` | `{similarity, source_type}` |
| `reasoning` | `{status}` |
| `classifying` | `{status}` |
| `classified` | `{query_type, confidence, searches}` |
| `fetching` | `{attempt, queries}` |
| `fetched` | `{pubmed_count, openfda_count}` |
| `evaluating` | `{attempt, status}` |
| `evaluated` | `{confident, confidence_score, missing}` |
| `synthesizing` | `{status}` |
| `complete` | `{status}` |
| `result` | Full pipeline result JSON |
| `error` | `{message}` |

---

## Engineering Decisions

<details>
<summary><strong>Why a retry loop for evidence fetching?</strong></summary>

The evaluator scores evidence sufficiency after each PubMed fetch. If confidence is below threshold, it generates a refined query and fetches again (up to `MAX_RETRY_LOOPS`). This mirrors how a clinician escalates from a broad search to a targeted MESH-term query when initial results are inconclusive.

</details>

<details>
<summary><strong>Why PubMedBERT for embeddings instead of OpenAI/BGE?</strong></summary>

General-purpose embeddings fail on medical terminology — "MI" in cardiology vs "MI" in neurology. PubMedBERT is pre-trained on 21M PubMed abstracts and encodes clinical concepts at a much higher fidelity, producing significantly better cache hit rates for semantically similar medical queries.

</details>

<details>
<summary><strong>Why India-specific reranking?</strong></summary>

A symptom cluster of "fever + joint pain" has fundamentally different differential probability in Maharashtra during monsoon (dengue, leptospirosis) versus winter (influenza, chikungunya). Generic models trained on Western epidemiology underweight these regionally dominant conditions. The `india_reranker` adjusts condition probabilities based on state-level seasonal outbreak data.

</details>

<details>
<summary><strong>Why faithfulness scoring post-synthesis?</strong></summary>

LLMs can produce confident-sounding claims not grounded in any retrieved evidence. The faithfulness checker cross-references every claim in the synthesis against the PubMed abstracts actually retrieved during that pipeline run, scores grounding quality, and flags low-confidence answers before they reach the user.

</details>

<details>
<summary><strong>Why is the PERSIST stage non-fatal?</strong></summary>

The `PERSIST` stage (Supabase writes for timeline, monitoring plans, tasks) is fully wrapped so a database failure cannot deny a patient their clinical analysis. The synthesis is always returned — persistence is best-effort.

</details>

---

## Deployment

Deployment is fully automated via GitHub Actions on every push to `main`.

| Target | Provider | Trigger |
|---|---|---|
| Backend | Render (Docker) | `push` to `main` |
| Frontend | Vercel | `push` to `main` |

```yaml
# .github/workflows/deploy.yml handles:
# - Docker build + push to registry
# - Render deploy webhook
# - Vercel deploy
```

---

## Evaluation

```bash
# Run the built-in evaluation suite (requires ADMIN_KEY)
curl -H "X-Admin-Key: your-admin-key" \
  "http://localhost:8000/api/evaluation/run?max_cases=5"
```

Returns per-case scores for:
- **Faithfulness** — claim-to-evidence grounding
- **Confidence** — evidence sufficiency score
- **Source coverage** — breadth of literature coverage
- **Retrieval attempts** — efficiency of the fetch loop

---

## RAG Memory Design

```
PubMed abstracts
      │
      ▼
PubMedBERT embeddings
      │
      ▼
ChromaDB vector store
      │
      ├── Similarity search (threshold: 0.85)
      │
      └── TTL-based cache expiry
            ├── Clinical guidelines:  7 days
            ├── Drug alerts:         24 hours
            └── Research papers:     30 days

Source trust weighting:
  WHO / CDC  → 10
  PubMed     →  8
  MedlinePlus →  7
```

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'feat: add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

Built by [Rudra Naresh](https://github.com/rudranaresh0201)

</div>
