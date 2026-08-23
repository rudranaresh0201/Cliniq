import hmac
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Load .env before any import that triggers module-level os.environ.get().
# workers.watch_worker → db.supabase_client reads env vars at import time,
# and config.py (which calls load_dotenv) is imported after watch_worker.
# Calling load_dotenv() here guarantees the env is populated first.
# ---------------------------------------------------------------------------
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
import os
print("GROQ KEY:", os.getenv("GROQ_API_KEY", "")[:15])

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from workers.watch_worker import on_startup, on_shutdown

from config import MAX_RETRY_LOOPS
from backend.safety.redflags import check_emergency
from backend.memory.rag import check_cache, store_result, get_cache_stats
from backend.agents.classifier_planner import classify_and_plan
from backend.agents.clinical_reasoner import reason_clinically
from backend.agents.evaluator import evaluate
from backend.agents.synthesizer import synthesize, DISCLAIMER
from backend.agents.faithfulness import check_faithfulness
from backend.agents.contradiction_detector import check_contradictions
from backend.retrieval.fetcher import fetch_all
from backend.observability.logger import log_event, StageTimer
from backend.models.patient import AnalyzeRequestV2
from backend.api.routes.patient import router as patient_router
from backend.api.routes.reports import router as reports_router
from backend.india.epidemiology import get_india_context, adjust_conditions_for_india
from backend.india.outbreak_monitor import get_outbreak_alerts

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()


app = FastAPI(
    title="ClinIQ Medical RAG API",
    description="Agentic AI for medical query analysis powered by Groq + PubMed + OpenFDA",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patient_router)
app.include_router(reports_router)

from api.v2.pipeline_router import router as v2_router  # noqa: E402
from api.v2.lab_ingestion import router as lab_ingestion_router  # noqa: E402
from routers.intelligence import router as intelligence_router  # noqa: E402
app.include_router(v2_router)
app.include_router(lab_ingestion_router)
app.include_router(intelligence_router, prefix="/api")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    age: int | None = Field(None, ge=0, le=150)
    gender: str | None = None
    medications: list[str] = Field(default_factory=list)
    existing_conditions: list[str] = Field(default_factory=list)
    state: str = "Maharashtra"


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

EmitFn = None  # type alias hint only

async def _run_pipeline(
    query: str,
    age: int | None,
    gender: str | None,
    medications: list[str],
    existing_conditions: list[str],
    emit=None,  # async callable(event: str, data: dict) | None
    state: str = "Maharashtra",
) -> dict:
    """
    Full RAG pipeline:
    safety → cache → classify → plan → fetch/evaluate loop → synthesize → store
    """

    async def _emit(event: str, data: dict):
        if emit is not None:
            await emit(event, data)

    patient_context = {
        "age": age,
        "gender": gender,
        "medications": medications,
        "existing_conditions": existing_conditions,
    }

    # ------------------------------------------------------------------
    # Stage 1: Safety / red-flag check
    # ------------------------------------------------------------------
    await _emit("safety_check", {"status": "Checking for emergency indicators…"})
    emergency = check_emergency(query)
    if emergency:
        await _emit("emergency", emergency)
        return {**emergency, "cached": False, "pipeline_stopped": "emergency_detected"}

    # ------------------------------------------------------------------
    # Stage 2: Cache lookup
    # ------------------------------------------------------------------
    await _emit("cache_check", {"status": "Checking knowledge cache…"})
    cached = check_cache(query)
    if cached:
        await _emit("cache_hit", {"similarity": cached["similarity"], "source_type": cached["source_type"]})
        try:
            answer = json.loads(cached["answer"])
        except (json.JSONDecodeError, TypeError):
            answer = {"patient_summary": cached["answer"]}
        return {
            **answer,
            "cached": True,
            "similarity": cached["similarity"],
            "metadata": {"cached": True, "source_type": cached["source_type"]},
        }

    await _emit("cache_miss", {"status": "No cache hit — starting full retrieval"})

    # ------------------------------------------------------------------
    # Stage 3: Clinical reasoning — deep first-principles analysis
    # ------------------------------------------------------------------
    await _emit("reasoning", {"status": "Reasoning clinically…"})
    india_ctx = get_india_context(state)
    clinical_reasoning = await reason_clinically(
        query=query,
        patient_context=patient_context,
        india_context=india_ctx,
    )

    # ------------------------------------------------------------------
    # Stage 4+5: Combined classify + plan (informed by clinical reasoning)
    # ------------------------------------------------------------------
    await _emit("classifying", {"status": "Classifying query and planning search…"})
    combined = await classify_and_plan(query, {
        "age": age,
        "state": state,
    }, clinical_reasoning=clinical_reasoning)
    await _emit("classified", {
        "query_type": combined["query_type"],
        "confidence": combined["confidence"],
        "requires_drug_check": combined["requires_drug_check"],
        "searches": combined["searches"],
        "strategy": combined["strategy"],
    })

    # Merge planner drugs with patient medications for drug checks
    all_drugs = list({d.lower() for d in (combined["drugs_to_check"] + medications)})

    # ------------------------------------------------------------------
    # Stage 5–6: Fetch → Evaluate loop (up to MAX_RETRY_LOOPS)
    # ------------------------------------------------------------------
    accumulated: dict = {"pubmed": [], "openfda": [], "total_sources": 0}
    searches = combined["searches"] or [query]
    evaluation: dict = {}
    attempt = 0

    for attempt in range(1, MAX_RETRY_LOOPS + 1):
        await _emit("fetching", {
            "attempt": attempt,
            "max_attempts": MAX_RETRY_LOOPS,
            "queries": searches,
        })

        fetched = await fetch_all(searches, combined["query_type"], all_drugs)

        # Deduplicate PubMed by PMID before accumulating
        existing_pmids = {a.get("pmid") for a in accumulated["pubmed"] if isinstance(a, dict)}
        for article in fetched.get("pubmed", []):
            if isinstance(article, dict) and article.get("pmid") not in existing_pmids:
                accumulated["pubmed"].append(article)
                existing_pmids.add(article.get("pmid"))
        accumulated["openfda"].extend(fetched.get("openfda", []))
        accumulated["total_sources"] = len(accumulated["pubmed"]) + len(accumulated["openfda"])

        await _emit("fetched", {
            "attempt": attempt,
            "pubmed_count": len(accumulated["pubmed"]),
            "openfda_count": len(accumulated["openfda"]),
        })

        await _emit("evaluating", {"attempt": attempt, "status": "Evaluating evidence sufficiency…"})
        evaluation = await evaluate(query, accumulated, attempt)
        await _emit("evaluated", {
            "attempt": attempt,
            "confident": evaluation["confident"],
            "confidence_score": evaluation["confidence_score"],
            "missing": evaluation.get("missing", ""),
        })

        if evaluation["confident"] or attempt == MAX_RETRY_LOOPS:
            break

        # Refine search for next iteration
        refined = evaluation.get("refined_query", "").strip()
        searches = [refined] if refined else [query]
        await _emit("refining", {"refined_query": searches[0]})

    # ------------------------------------------------------------------
    # Stage 7: Synthesis
    # ------------------------------------------------------------------
    await _emit("synthesizing", {"status": "Synthesizing final answer…"})
    result = await synthesize(
        query, accumulated, combined["query_type"], patient_context,
        india_ctx, clinical_reasoning=clinical_reasoning,
    )

    # ------------------------------------------------------------------
    # Stage 8: Faithfulness + contradiction checks
    # ------------------------------------------------------------------
    faithfulness = await check_faithfulness(
        retrieved_chunks=accumulated.get("pubmed", []),
        generated_answer=str(result.get("conditions", [])),
    )
    result["faithfulness_score"] = faithfulness.get("faithfulness_score", 0.5)
    result["faithfulness_verdict"] = faithfulness.get("verdict", "unverifiable")

    if faithfulness.get("faithfulness_score", 1.0) < 0.4:
        result["reliability_warning"] = (
            "Some claims may not be fully supported by retrieved evidence. "
            "Please verify with a doctor."
        )

    contradiction_check = await check_contradictions(query, result)
    if contradiction_check.get("contradictions_found"):
        result["contradictions"] = contradiction_check.get("contradictions", [])

    # Expose clinical reasoning summary in result
    result["clinical_reasoning"] = {
        "pattern": clinical_reasoning.get("clinical_pattern", ""),
        "unifying_hypothesis": clinical_reasoning.get("unifying_hypothesis", ""),
        "most_important_question": clinical_reasoning.get("most_important_question", ""),
        "reasoning_summary": clinical_reasoning.get("reasoning_summary", ""),
    }

    # ------------------------------------------------------------------
    # Stage 9: Cache storage
    # ------------------------------------------------------------------
    source_type = "pubmed" if accumulated["pubmed"] else "general"
    store_result(query, json.dumps(result), source_type)

    result["metadata"] = {
        "query_type": combined["query_type"],
        "classification_confidence": combined["confidence"],
        "sources_consulted": accumulated["total_sources"],
        "pubmed_articles": len(accumulated["pubmed"]),
        "openfda_records": len(accumulated["openfda"]),
        "retrieval_attempts": attempt,
        "final_confidence_score": evaluation.get("confidence_score", 0),
        "faithfulness_score": result.get("faithfulness_score", 0.5),
        "faithfulness_verdict": result.get("faithfulness_verdict", "unverifiable"),
        "cached": False,
    }

    await _emit("complete", {"status": "Analysis complete"})
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "ClinIQ Medical RAG",
        "timestamp": time.time(),
    }


@app.get("/api/cache/stats")
async def cache_stats():
    return get_cache_stats()


@app.post("/api/analyze")
async def analyze(body: AnalyzeRequest):
    try:
        result = await _run_pipeline(
            query=body.query,
            age=body.age,
            gender=body.gender,
            medications=body.medications,
            existing_conditions=body.existing_conditions,
            state=body.state,
        )

        india_ctx = get_india_context(body.state)
        if result.get("conditions"):
            result["conditions"] = adjust_conditions_for_india(
                conditions=result["conditions"],
                india_context=india_ctx,
                query=body.query,
            )
        result["india_context"] = {
            "season": india_ctx["season"],
            "high_risk_diseases": india_ctx["high_risk_diseases"],
            "regional_alerts": get_outbreak_alerts(body.state),
            "epidemiological_note": india_ctx["context_string"],
        }

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/v2")
async def analyze_v2(body: AnalyzeRequestV2):
    """
    Extended analyze endpoint with longitudinal patient tracking.

    If user_id is provided:
    - Loads the patient's profile and injects history context into the query
    - Saves the completed episode to the database
    - Runs timeline analysis automatically when 3+ episodes exist
    """
    from backend.db.database import get_patient_profile, save_episode, get_patient_history
    from backend.agents.timeline import analyze_timeline

    user_id = body.user_id
    medications = body.medications
    existing_conditions = body.existing_conditions
    age = body.age
    gender = body.gender

    # Enrich context from stored patient profile when user_id provided
    history_context = ""
    if user_id:
        try:
            profile = get_patient_profile(user_id)
            if profile:
                if not age and profile.get("age"):
                    age = profile["age"]
                if not gender and profile.get("gender"):
                    gender = profile["gender"]
                if not medications:
                    medications = profile.get("medications", [])
                if not existing_conditions:
                    existing_conditions = profile.get("existing_conditions", [])

                past = profile.get("history", [])[:5]
                if past:
                    snippets = "; ".join(
                        f"[{ep.get('timestamp', '')[:10]}] {ep.get('triage','?')}: {ep.get('query','')[:80]}"
                        for ep in past
                    )
                    history_context = f" [Patient history: {snippets}]"
        except Exception as e:
            log_event("v2.profile_load_error", {"error": str(e)}, level="warning")

    enriched_query = body.query + history_context

    with StageTimer("v2.pipeline", {"user_id": user_id or "anonymous"}):
        try:
            result = await _run_pipeline(
                query=enriched_query,
                age=age,
                gender=gender,
                medications=medications,
                existing_conditions=existing_conditions,
                state=body.state,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Persist episode and optionally run timeline
    timeline = None
    if user_id:
        print(f"[ClinIQ] Saving episode for user: {user_id}")
        try:
            conditions_flagged = [c["name"] for c in result.get("conditions", [])]
            save_episode(
                user_id=user_id,
                query=body.query,
                response=result,
                triage=result.get("triage", "INFORMATIONAL"),
                conditions_flagged=conditions_flagged,
            )

            history = get_patient_history(user_id, limit=20)
            if len(history) >= 3:
                timeline = await analyze_timeline(history)
        except Exception as e:
            log_event("v2.post_save_error", {"error": str(e)}, level="warning")

    if timeline:
        result["timeline_analysis"] = timeline

    return result


@app.get("/api/evaluation/run")
async def run_evaluation(
    max_cases: int = Query(5, ge=1, le=10),
    x_admin_key: str | None = Header(default=None),
):
    admin_key = os.environ.get("ADMIN_KEY", "")
    if not admin_key or not x_admin_key or not hmac.compare_digest(x_admin_key, admin_key):
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Key header")

    from backend.evaluation.metrics import run_evaluation_suite

    async def _analyze_fn(query: str) -> dict:
        return await _run_pipeline(query=query, age=None, gender=None, medications=[], existing_conditions=[])

    report = await run_evaluation_suite(_analyze_fn, max_cases=max_cases)
    return report


@app.get("/api/analyze/stream")
async def analyze_stream(
    query: str = Query(..., min_length=3, max_length=1000),
    age: int | None = Query(None),
    gender: str | None = Query(None),
    medications: str = Query(""),       # comma-separated
    existing_conditions: str = Query(""),  # comma-separated
):
    """
    SSE endpoint. Emits events for each pipeline stage so the frontend
    can show real-time progress.

    Event format:
        event: <stage_name>
        data: <json payload>
    """
    meds = [m.strip() for m in medications.split(",") if m.strip()]
    conditions = [c.strip() for c in existing_conditions.split(",") if c.strip()]

    async def event_stream() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue = asyncio.Queue()

        async def emit(event: str, data: dict):
            await queue.put((event, data))

        async def run():
            try:
                result = await _run_pipeline(
                    query=query,
                    age=age,
                    gender=gender,
                    medications=meds,
                    existing_conditions=conditions,
                    emit=emit,
                )
                # Emit the final payload under a dedicated "result" event
                await queue.put(("result", result))
            except Exception as e:
                await queue.put(("error", {"message": str(e)}))
            finally:
                await queue.put(None)  # sentinel — stream is done

        task = asyncio.create_task(run())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event_name, payload = item
                yield f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
