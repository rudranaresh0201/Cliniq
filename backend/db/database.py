import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("cliniq")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Use local file storage when Supabase is not configured
_USE_LOCAL = not (SUPABASE_URL and SUPABASE_KEY)

# ---------------------------------------------------------------------------
# Local file-based storage
# ---------------------------------------------------------------------------

DATA_DIR = Path("logs/patient_data")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_patient_file(user_id: str) -> Path:
    return DATA_DIR / f"{user_id}.json"


def _load_patient(user_id: str) -> dict:
    f = _get_patient_file(user_id)
    if f.exists():
        return json.loads(f.read_text())
    return {"user_id": user_id, "episodes": [], "profile": {}}


def _save_patient(user_id: str, data: dict):
    _get_patient_file(user_id).write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Supabase client (lazy, only initialised when _USE_LOCAL is False)
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    from supabase import create_client
    _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ---------------------------------------------------------------------------
# Patient profile
# ---------------------------------------------------------------------------

def create_patient(
    user_id: str,
    age: int | None = None,
    gender: str | None = None,
    existing_conditions: list[str] | None = None,
    medications: list[str] | None = None,
) -> dict:
    if _USE_LOCAL:
        data = _load_patient(user_id)
        data["profile"] = {
            "user_id": user_id,
            "age": age,
            "gender": gender,
            "existing_conditions": existing_conditions or [],
            "medications": medications or [],
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        _save_patient(user_id, data)
        return data["profile"]

    try:
        db = _get_client()
        row = {
            "id": user_id,
            "age": age,
            "gender": gender,
            "existing_conditions": existing_conditions or [],
            "medications": medications or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = db.table("patients").upsert(row).execute()
        return result.data[0] if result.data else row
    except Exception as e:
        logger.error(f"create_patient failed: {e}")
        raise


def get_patient(user_id: str) -> dict | None:
    if _USE_LOCAL:
        return _load_patient(user_id).get("profile") or None

    try:
        db = _get_client()
        result = db.table("patients").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"get_patient failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Episode history
# ---------------------------------------------------------------------------

def save_episode(
    user_id: str,
    query: str,
    response: dict,
    triage: str,
    conditions_flagged: list[str],
) -> dict:
    if _USE_LOCAL:
        data = _load_patient(user_id)
        episode = {
            "id": f"ep_{int(time.time())}",
            "patient_id": user_id,
            "query": query,
            "triage": triage,
            "conditions": conditions_flagged,
            "response_summary": response.get("patient_summary", ""),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        data["episodes"].append(episode)
        _save_patient(user_id, data)
        return episode

    try:
        db = _get_client()
        row = {
            "patient_id": user_id,
            "query": query[:1000],
            "triage": triage,
            "conditions": conditions_flagged,
            "response_summary": response.get("patient_summary", "")[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        result = db.table("health_episodes").insert(row).execute()
        return result.data[0] if result.data else row
    except Exception as e:
        logger.error(f"save_episode failed: {e}")
        return {}


def get_patient_history(user_id: str, limit: int = 20) -> list[dict]:
    if _USE_LOCAL:
        episodes = _load_patient(user_id).get("episodes", [])
        return sorted(episodes, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

    try:
        db = _get_client()
        result = (
            db.table("health_episodes")
            .select("*")
            .eq("patient_id", user_id)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"get_patient_history failed: {e}")
        return []


def get_patient_profile(user_id: str) -> dict:
    if _USE_LOCAL:
        data = _load_patient(user_id)
        profile = data.get("profile", {})
        profile["history"] = get_patient_history(user_id, limit=5)
        return profile

    profile = get_patient(user_id) or {}
    history = get_patient_history(user_id)
    return {**profile, "history": history}


# ---------------------------------------------------------------------------
# Medication updates
# ---------------------------------------------------------------------------

def update_medications(user_id: str, medications: list[str]) -> dict:
    if _USE_LOCAL:
        data = _load_patient(user_id)
        data.setdefault("profile", {})["medications"] = medications
        _save_patient(user_id, data)
        return data["profile"]

    try:
        db = _get_client()
        result = (
            db.table("patients")
            .update({"medications": medications})
            .eq("id", user_id)
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception as e:
        logger.error(f"update_medications failed: {e}")
        raise
