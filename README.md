# ClinIQ — India-Aware Medical Intelligence Platform

AI-powered medical analysis system that thinks like an Indian clinician.

## Features
- Agentic RAG pipeline (classify → plan → fetch → evaluate → synthesize)
- India-specific disease reranking (dengue, malaria, typhoid priority)
- Real PubMed citations for every answer
- Drug interaction checking via OpenFDA
- Lab report interpretation (CBC, LFT, X-ray, prescriptions)
- Patient history and longitudinal tracking
- Streaming SSE (live agent thinking)
- Emergency safety layer (hardcoded, no LLM)
- Triage: EMERGENCY / URGENT / ROUTINE / INFORMATIONAL

## Tech Stack
- FastAPI + Python
- React + TypeScript + Tailwind
- ChromaDB vector memory
- Groq LLM (llama-3.3-70b)
- SentenceTransformers embeddings
- PubMed API + OpenFDA API

## Setup
```bash
# Backend
pip install -r requirements.txt
cp .env.example .env
# Add your GROQ_API_KEY to .env
python -m uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Architecture
Request → Safety Check → Cache → Classify → Plan →
Fetch (PubMed + OpenFDA) → Evaluate → Synthesize →
India Reranking → Plausibility Filter → Response
