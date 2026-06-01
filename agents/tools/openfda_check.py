"""
ClinIQ 2.0 — openfda_check tool.

Replaces the registry stub.  Three-step OpenFDA flow:
  1. drug/label.json  → warnings, contraindications, interactions text
  2. drug/event.json  → top-5 most-reported adverse reactions (counts)
  3. India / Jan Aushadhi availability — pure local lookup (no API call)
"""

import logging
from typing import Any

import httpx

from agents.tool_registry import REGISTRY, Tool

logger = logging.getLogger("cliniq.tools.openfda_check")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LABEL_URL = "https://api.fda.gov/drug/label.json"
_EVENT_URL = "https://api.fda.gov/drug/event.json"
_HTTP_TIMEOUT = 10.0
_TEXT_PREVIEW_CHARS = 400   # truncation limit for label text fields
_TOP_REACTIONS_LIMIT = 5

# ---------------------------------------------------------------------------
# India drug availability data
# ---------------------------------------------------------------------------

INDIA_COMMON_DRUGS: frozenset[str] = frozenset(
    {
        "metformin", "amlodipine", "atorvastatin", "paracetamol",
        "amoxicillin", "azithromycin", "ciprofloxacin", "metronidazole",
        "omeprazole", "pantoprazole", "ranitidine", "cetirizine",
        "montelukast", "salbutamol", "budesonide", "prednisolone",
        "hydroxychloroquine", "chloroquine", "primaquine", "artemether",
        "doxycycline", "rifampicin", "isoniazid", "pyrazinamide", "ethambutol",
        "streptomycin", "ceftriaxone", "piperacillin", "meropenem",
        "vancomycin", "furosemide", "spironolactone", "atenolol",
        "metoprolol", "ramipril", "enalapril", "losartan", "aspirin",
        "clopidogrel", "warfarin", "heparin", "insulin", "glipizide",
        "glibenclamide", "levothyroxine", "hydrocortisone", "dexamethasone",
        "diclofenac", "ibuprofen", "tramadol",
    }
)

_JAN_AUSHADHI_NOTE = "Available at Jan Aushadhi Kendras at reduced cost"

# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


def _fallback(drug_name: str, error: str) -> dict:
    return {
        "drug_name": drug_name,
        "warnings": [],
        "contraindications": [],
        "top_adverse_reactions": [],
        "drug_interactions_text": "",
        "india_available": False,
        "jan_aushadhi_available": False,
        "jan_aushadhi_note": "",
        "data_source": "OpenFDA",
        "error": error,
    }


# ---------------------------------------------------------------------------
# Step 1 — drug label
# ---------------------------------------------------------------------------


async def _fetch_label(client: httpx.AsyncClient, drug_name: str) -> dict[str, Any] | None:
    """Return the first label result for the drug, or None if not found."""
    params = {
        "search": f'openfda.generic_name:"{drug_name}"',
        "limit": "1",
    }
    try:
        resp = await client.get(_LABEL_URL, params=params)
        if resp.status_code == 404:
            logger.info("openfda label: no results for %r", drug_name)
            return None
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0] if results else None
    except httpx.HTTPStatusError as exc:
        logger.warning("openfda label HTTP %d for %r", exc.response.status_code, drug_name)
        return None


def _extract_field(label: dict, field: str) -> list[str]:
    """Return a list of truncated text strings from a label field."""
    raw: list[str] = label.get(field, [])
    out: list[str] = []
    for item in raw:
        text = item.strip()
        if text:
            out.append(text[:_TEXT_PREVIEW_CHARS] + ("…" if len(text) > _TEXT_PREVIEW_CHARS else ""))
    return out


# ---------------------------------------------------------------------------
# Step 2 — adverse events
# ---------------------------------------------------------------------------


async def _fetch_adverse_events(
    client: httpx.AsyncClient, drug_name: str
) -> list[dict]:
    """Return top-N most-reported MedDRA reaction terms with counts."""
    params = {
        "search": f'patient.drug.medicinalproduct:"{drug_name}"',
        "count": "patient.reaction.reactionmeddrapt.exact",
        "limit": str(_TOP_REACTIONS_LIMIT),
    }
    try:
        resp = await client.get(_EVENT_URL, params=params)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [
            {"reaction": r.get("term", ""), "count": r.get("count", 0)}
            for r in results
        ]
    except httpx.HTTPStatusError as exc:
        logger.warning("openfda events HTTP %d for %r", exc.response.status_code, drug_name)
        return []


# ---------------------------------------------------------------------------
# Step 3 — India / Jan Aushadhi availability
# ---------------------------------------------------------------------------


def _india_availability(drug_name: str) -> tuple[bool, bool, str]:
    """
    Returns (india_available, jan_aushadhi_available, jan_aushadhi_note).
    Matches on any word in the drug name against the common drugs set so
    that compound names like "artemether lumefantrine" are handled.
    """
    tokens = drug_name.lower().split()
    available = any(tok in INDIA_COMMON_DRUGS for tok in tokens)
    if available:
        return True, True, _JAN_AUSHADHI_NOTE
    return False, False, ""


# ---------------------------------------------------------------------------
# Interaction cross-check (local, no API call)
# ---------------------------------------------------------------------------


def _flag_interactions(
    interactions_text: str, check_interactions: list[str]
) -> list[str]:
    """
    Return names from check_interactions that appear in the label's
    drug_interactions text — simple case-insensitive substring match.
    """
    lower_text = interactions_text.lower()
    return [drug for drug in check_interactions if drug.lower() in lower_text]


# ---------------------------------------------------------------------------
# Main tool function
# ---------------------------------------------------------------------------


async def check_drug_safety(inputs: dict) -> dict:
    """
    Check FDA drug safety data and India market availability.

    Steps 1–2 hit OpenFDA APIs concurrently via a single AsyncClient
    connection pool.  Step 3 is local.
    """
    drug_name: str = inputs.get("drug_name", "").strip()
    check_interactions: list[str] = inputs.get("check_interactions", [])

    if not drug_name:
        logger.warning("check_drug_safety called with empty drug_name")
        return _fallback("", "empty_drug_name")

    logger.info(
        "check_drug_safety | drug=%r | interactions_to_check=%d",
        drug_name, len(check_interactions),
    )

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            # Steps 1 and 2 — label then events (sequential to respect rate limits)
            label = await _fetch_label(client, drug_name)
            adverse_events = await _fetch_adverse_events(client, drug_name)
    except httpx.TimeoutException:
        logger.error("check_drug_safety: OpenFDA request timed out for %r", drug_name)
        return _fallback(drug_name, "openfda_unavailable")
    except Exception:
        logger.exception("check_drug_safety: unexpected error for %r", drug_name)
        return _fallback(drug_name, "openfda_unavailable")

    # Extract label fields (gracefully handles None label)
    warnings: list[str] = _extract_field(label, "warnings") if label else []
    contraindications: list[str] = _extract_field(label, "contraindications") if label else []
    interactions_parts: list[str] = _extract_field(label, "drug_interactions") if label else []
    drug_interactions_text: str = " ".join(interactions_parts)

    # Flag any check_interactions drugs found in the label text
    flagged = _flag_interactions(drug_interactions_text, check_interactions)
    if flagged:
        logger.info(
            "check_drug_safety: interaction signal for %r with %s", drug_name, flagged
        )
        drug_interactions_text = (
            f"[!] Potential interaction detected with: {', '.join(flagged)}. "
            + drug_interactions_text
        )

    # Step 3 — India availability
    india_available, jan_available, jan_note = _india_availability(drug_name)

    logger.info(
        "check_drug_safety OK | drug=%r | warnings=%d | adverse=%d | india=%s",
        drug_name, len(warnings), len(adverse_events), india_available,
    )

    return {
        "drug_name": drug_name,
        "warnings": warnings,
        "contraindications": contraindications,
        "top_adverse_reactions": adverse_events,
        "drug_interactions_text": drug_interactions_text,
        "india_available": india_available,
        "jan_aushadhi_available": jan_available,
        "jan_aushadhi_note": jan_note,
        "data_source": "OpenFDA",
    }


# ---------------------------------------------------------------------------
# Re-register with real implementation
# ---------------------------------------------------------------------------

REGISTRY.register(
    Tool(
        name="openfda_check",
        description="Check drug safety, interactions, and Indian market availability",
        input_schema={
            "type": "object",
            "properties": {
                "drug_name":          {"type": "string"},
                "check_interactions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["drug_name"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "drug_name":              {"type": "string"},
                "warnings":               {"type": "array"},
                "contraindications":      {"type": "array"},
                "top_adverse_reactions":  {"type": "array"},
                "drug_interactions_text": {"type": "string"},
                "india_available":        {"type": "boolean"},
                "jan_aushadhi_available": {"type": "boolean"},
                "jan_aushadhi_note":      {"type": "string"},
                "data_source":            {"type": "string"},
            },
        },
        agent="drug_safety_agent",
        async_fn=check_drug_safety,
    )
)

logger.debug("openfda_check: real implementation registered")
