"""
ClinIQ 2.0 — india_epidemiology_reranker tool.

Replaces the registry stub.  Pure Python — no LLM call.
Applies rule-based confidence boosts to differentials based on Indian
season, geographic location, and patient age, then re-sorts and flags
what context was applied.
"""

import logging
from datetime import datetime, timezone

from agents.tool_registry import REGISTRY, Tool

logger = logging.getLogger("cliniq.tools.india_reranker")

# ---------------------------------------------------------------------------
# Tunable boost constants — change here, nowhere else
# ---------------------------------------------------------------------------

MONSOON_BOOST: float = 0.15
WINTER_BOOST: float = 0.10
MALARIA_HIGH_ZONE_BOOST: float = 0.20
URBAN_DENSITY_BOOST: float = 0.10
CHILD_BOOST: float = 0.15        # age < 5
YOUNG_ADULT_BOOST: float = 0.10  # age 5–25
OLDER_ADULT_BOOST: float = 0.10  # age > 50
CONFIDENCE_CAP: float = 0.95

# ---------------------------------------------------------------------------
# Seasonal disease maps  {lowercase keyword → boost amount}
# ---------------------------------------------------------------------------

_MONSOON_DISEASES: dict[str, float] = {
    "dengue":        MONSOON_BOOST,
    "malaria":       MONSOON_BOOST,
    "leptospirosis": MONSOON_BOOST,
    "typhoid":       MONSOON_BOOST,
    "chikungunya":   MONSOON_BOOST,
    "hepatitis a":   MONSOON_BOOST,
    "cholera":       MONSOON_BOOST,
}

_WINTER_DISEASES: dict[str, float] = {
    "influenza":           WINTER_BOOST,
    "pneumonia":           WINTER_BOOST,
    "copd":                WINTER_BOOST,
    "asthma":              WINTER_BOOST,
    "uri":                 WINTER_BOOST,
    "upper respiratory":   WINTER_BOOST,
}

# ---------------------------------------------------------------------------
# Location maps
# ---------------------------------------------------------------------------

_MALARIA_HIGH_ZONES: list[str] = [
    "odisha", "jharkhand", "chhattisgarh", "manipur", "meghalaya",
    "tripura", "assam", "arunachal", "nagaland", "mizoram",
]

_URBAN_METROS: list[str] = [
    "mumbai", "delhi", "kolkata", "chennai", "bangalore", "hyderabad", "pune",
]

_URBAN_DISEASE_BOOSTS: dict[str, float] = {
    "dengue":  URBAN_DENSITY_BOOST,
    "typhoid": URBAN_DENSITY_BOOST,
}

# ---------------------------------------------------------------------------
# Age-based disease maps  {lowercase keyword → boost amount}
# ---------------------------------------------------------------------------

_CHILD_DISEASES: dict[str, float] = {
    "rotavirus":     CHILD_BOOST,
    "pneumonia":     CHILD_BOOST,
    "malnutrition":  CHILD_BOOST,
}

_YOUNG_ADULT_DISEASES: dict[str, float] = {
    "typhoid": YOUNG_ADULT_BOOST,
    "dengue":  YOUNG_ADULT_BOOST,
}

_OLDER_ADULT_DISEASES: dict[str, float] = {
    "tuberculosis": OLDER_ADULT_BOOST,
    "tb":           OLDER_ADULT_BOOST,
    "diabetes":     OLDER_ADULT_BOOST,
    "cardiac":      OLDER_ADULT_BOOST,
    "heart":        OLDER_ADULT_BOOST,
}

# ---------------------------------------------------------------------------
# Season detection
# ---------------------------------------------------------------------------

_MONTH_TO_SEASON: dict[int, str] = {
    12: "winter", 1: "winter", 2: "winter",
    3: "summer", 4: "summer", 5: "summer",
    6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon",
    10: "post_monsoon", 11: "post_monsoon",
}


def _detect_season() -> str:
    month = datetime.now(tz=timezone.utc).month
    return _MONTH_TO_SEASON.get(month, "unknown")


# ---------------------------------------------------------------------------
# Boost helpers — each returns (boost_delta, flag_string | None)
# ---------------------------------------------------------------------------


def _seasonal_boost(
    diagnosis_lower: str, season: str
) -> tuple[float, str | None]:
    if season == "monsoon":
        for keyword, amount in _MONSOON_DISEASES.items():
            if keyword in diagnosis_lower:
                return amount, f"Monsoon season — {keyword} confidence boosted"
    elif season == "winter":
        for keyword, amount in _WINTER_DISEASES.items():
            if keyword in diagnosis_lower:
                return amount, f"Winter season — {keyword} confidence boosted"
    return 0.0, None


def _location_boost(
    diagnosis_lower: str, location_lower: str
) -> tuple[float, str | None]:
    # High-zone malaria check
    for zone in _MALARIA_HIGH_ZONES:
        if zone in location_lower and "malaria" in diagnosis_lower:
            return (
                MALARIA_HIGH_ZONE_BOOST,
                f"High malaria zone detected — {zone.title()} location",
            )
    # Urban density check
    for metro in _URBAN_METROS:
        if metro in location_lower:
            for keyword, amount in _URBAN_DISEASE_BOOSTS.items():
                if keyword in diagnosis_lower:
                    return (
                        amount,
                        f"Urban density effect — {keyword} boosted for {metro.title()}",
                    )
    return 0.0, None


def _age_boost(
    diagnosis_lower: str, age: int | None
) -> tuple[float, str | None]:
    if age is None:
        return 0.0, None
    if age < 5:
        for keyword, amount in _CHILD_DISEASES.items():
            if keyword in diagnosis_lower:
                return amount, f"Paediatric patient (age {age}) — {keyword} boosted"
    elif 5 <= age <= 25:
        for keyword, amount in _YOUNG_ADULT_DISEASES.items():
            if keyword in diagnosis_lower:
                return amount, f"Young adult (age {age}) — {keyword} boosted"
    elif age > 50:
        for keyword, amount in _OLDER_ADULT_DISEASES.items():
            if keyword in diagnosis_lower:
                return amount, f"Older adult (age {age}) — {keyword} boosted"
    return 0.0, None


# ---------------------------------------------------------------------------
# Location context summary
# ---------------------------------------------------------------------------


def _describe_location(location_lower: str) -> str:
    parts: list[str] = []
    for zone in _MALARIA_HIGH_ZONES:
        if zone in location_lower:
            parts.append(f"high-malaria zone ({zone.title()})")
            break
    for metro in _URBAN_METROS:
        if metro in location_lower:
            parts.append(f"urban metro ({metro.title()})")
            break
    return ", ".join(parts) if parts else "standard Indian context"


# ---------------------------------------------------------------------------
# Main tool function
# ---------------------------------------------------------------------------


async def rerank_for_india(inputs: dict) -> dict:
    """
    Rerank differential diagnoses using India-specific seasonal, geographic,
    and demographic boost rules.  No external calls — pure Python logic.
    """
    differentials: list[dict] = inputs.get("differentials", [])
    location: str = inputs.get("location", "")
    patient_age: int | None = inputs.get("patient_age")

    # Step 1 — season
    season: str = inputs.get("season") or _detect_season()

    location = location or ""
    location_lower = location.lower()
    location_context = _describe_location(location_lower)

    logger.info(
        "rerank_for_india | differentials=%d | season=%s | location=%s | age=%s",
        len(differentials), season, location or "unknown", patient_age,
    )

    if not differentials:
        logger.warning("rerank_for_india called with empty differentials")
        return {
            "reranked_differentials": [],
            "india_specific_flags": [],
            "season_detected": season,
            "location_context": location_context,
        }

    # Steps 2–4 — boost, cap, collect flags
    flags: set[str] = set()
    reranked: list[dict] = []

    for diff in differentials:
        entry = dict(diff)  # never mutate the caller's object
        diagnosis_lower = entry.get("diagnosis", "").lower()
        original_confidence = float(entry.get("confidence", 0.5))
        total_boost = 0.0

        for boost_fn in (
            lambda d: _seasonal_boost(d, season),
            lambda d: _location_boost(d, location_lower),
            lambda d: _age_boost(d, patient_age),
        ):
            delta, flag = boost_fn(diagnosis_lower)
            total_boost += delta
            if flag:
                flags.add(flag)

        # Step 3 — cap
        entry["confidence"] = min(CONFIDENCE_CAP, original_confidence + total_boost)
        reranked.append(entry)

    # Step 4 — re-sort
    reranked.sort(key=lambda d: float(d.get("confidence", 0.0)), reverse=True)

    logger.info(
        "rerank_for_india OK | season=%s | flags=%d | top=%s (%.2f)",
        season,
        len(flags),
        reranked[0].get("diagnosis", "?"),
        reranked[0].get("confidence", 0.0),
    )

    return {
        "reranked_differentials": reranked,
        "india_specific_flags": sorted(flags),
        "season_detected": season,
        "location_context": location_context,
    }


# ---------------------------------------------------------------------------
# Re-register with real implementation
# ---------------------------------------------------------------------------

REGISTRY.register(
    Tool(
        name="india_epidemiology_reranker",
        description="Rerank differentials using India-specific disease prevalence and seasonal patterns",
        input_schema={
            "type": "object",
            "properties": {
                "differentials": {"type": "array"},
                "location":      {"type": "string"},
                "season":        {"type": "string"},
                "patient_age":   {"type": "integer"},
            },
            "required": ["differentials"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "reranked_differentials": {"type": "array"},
                "india_specific_flags":   {"type": "array", "items": {"type": "string"}},
                "season_detected":        {"type": "string"},
                "location_context":       {"type": "string"},
            },
        },
        agent="clinical_agent",
        async_fn=rerank_for_india,
    )
)

logger.debug("india_epidemiology_reranker: real implementation registered")
