"""
ClinIQ 2.0 — CBC (Complete Blood Count) DeepDive interpreter.

Three-layer interpretation:
  1. Regex parsing  — extracts numeric values from raw lab text,
     handles Indian number formats (commas in WBC / platelets)
  2. Rule engine    — flags abnormals against age/sex-adjusted
     reference ranges, detects India-common CBC patterns
  3. Groq synthesis — hematology specialist prompt produces
     clinical summary, risk level, and actionable guidance

Designed to be called from agents/tools/deepdive/__init__.py.
"""

import json
import logging
import os
import re
from typing import Any

from groq import AsyncGroq

logger = logging.getLogger("cliniq.tools.deepdive.cbc")

_GROQ_MODEL = "llama-3.3-70b-versatile"

# ===========================================================================
# Reference ranges — (low, high) inclusive
# ===========================================================================

MALE_RANGES: dict[str, tuple[float, float]] = {
    "hemoglobin":  (13.5, 17.5),
    "rbc":         (4.5,  5.9),
    "hematocrit":  (41.0, 53.0),
    "mcv":         (80.0, 100.0),
    "mch":         (27.0, 33.0),
    "mchc":        (32.0, 36.0),
    "rdw":         (11.5, 14.5),
    "wbc":         (4.5,  11.0),
    "neutrophils": (40.0, 70.0),
    "lymphocytes": (20.0, 40.0),
    "monocytes":   (2.0,  10.0),
    "eosinophils": (1.0,  6.0),
    "basophils":   (0.0,  2.0),
    "platelets":   (150.0, 400.0),
    "mpv":         (7.5,  12.5),
}

FEMALE_RANGES: dict[str, tuple[float, float]] = {
    "hemoglobin":  (12.0, 15.5),
    "rbc":         (4.0,  5.2),
    "hematocrit":  (36.0, 46.0),
    "mcv":         (80.0, 100.0),
    "mch":         (27.0, 33.0),
    "mchc":        (32.0, 36.0),
    "rdw":         (11.5, 14.5),
    "wbc":         (4.5,  11.0),
    "neutrophils": (40.0, 70.0),
    "lymphocytes": (20.0, 40.0),
    "monocytes":   (2.0,  10.0),
    "eosinophils": (1.0,  6.0),
    "basophils":   (0.0,  2.0),
    "platelets":   (150.0, 400.0),
    "mpv":         (7.5,  12.5),
}

PEDIATRIC_RANGES: dict[str, tuple[float, float]] = {
    "hemoglobin":  (11.0, 16.0),
    "wbc":         (5.0,  15.0),
    "platelets":   (150.0, 400.0),
    "neutrophils": (30.0, 65.0),
    "lymphocytes": (25.0, 60.0),
}

CRITICAL_VALUES: dict[str, dict[str, float]] = {
    "hemoglobin": {"low": 7.0,   "high": 20.0},
    "wbc":        {"low": 2.0,   "high": 30.0},
    "platelets":  {"low": 50.0,  "high": 1000.0},
    "neutrophils": {"low": 10.0, "high": 90.0},
}

# ===========================================================================
# Compiled regex patterns — module-level for zero recompilation cost
# ===========================================================================

MARKER_PATTERNS: dict[str, re.Pattern] = {
    "hemoglobin": re.compile(
        r"(?:h[ae]m(?:o)?globin|hgb|hb)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "rbc": re.compile(
        r"(?:rbc|red\s*blood\s*cell|erythrocyte)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "hematocrit": re.compile(
        r"(?:hematocrit|haematocrit|hct|pcv)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "mcv": re.compile(r"mcv\s*[:\-]?\s*([\d.]+)", re.IGNORECASE),
    "mch": re.compile(r"\bmch\b\s*[:\-]?\s*([\d.]+)", re.IGNORECASE),
    "mchc": re.compile(r"mchc\s*[:\-]?\s*([\d.]+)", re.IGNORECASE),
    "rdw": re.compile(r"rdw\s*[:\-]?\s*([\d.]+)", re.IGNORECASE),
    "wbc": re.compile(
        r"(?:wbc|tlc|total\s*(?:leukocyte|leucocyte|wbc)\s*count)\s*[:\-]?\s*([\d,.]+)",
        re.IGNORECASE,
    ),
    "neutrophils": re.compile(
        r"(?:neutrophil|polymorphs|poly|pmn|seg)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "lymphocytes": re.compile(
        r"lymphocyte\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "monocytes": re.compile(
        r"monocyte\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "eosinophils": re.compile(
        r"eosinophil\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "basophils": re.compile(
        r"basophil\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "platelets": re.compile(
        r"(?:platelet|plt|thrombocyte)\s*(?:count)?\s*[:\-]?\s*([\d,.]+)",
        re.IGNORECASE,
    ),
    "mpv": re.compile(r"mpv\s*[:\-]?\s*([\d.]+)", re.IGNORECASE),
}

# ===========================================================================
# CBC pattern library — India-tuned, ordered by clinical priority
# ===========================================================================

PATTERNS: list[dict[str, Any]] = [
    {
        "name": "Iron Deficiency Anemia",
        "criteria": {"hemoglobin": "low", "mcv": "low", "mch": "low", "mchc": "low", "rdw": "high"},
        "confidence_base": 0.85,
        "india_common": True,
        "note": "Most common anemia in India, especially women and children",
    },
    {
        "name": "Megaloblastic Anemia (B12/Folate)",
        "criteria": {"hemoglobin": "low", "mcv": "high", "rdw": "high"},
        "confidence_base": 0.80,
        "india_common": True,
        "note": "Common in vegetarians — check serum B12 and folate",
    },
    {
        "name": "Dengue Pattern",
        "criteria": {"platelets": "low", "wbc": "low"},
        "confidence_base": 0.75,
        "india_common": True,
        "note": "Thrombocytopenia with leukopenia — dengue highly suspected in monsoon",
    },
    {
        "name": "Typhoid Pattern (Leukopenia)",
        "criteria": {"wbc": "low", "neutrophils": "low"},
        "confidence_base": 0.70,
        "india_common": True,
        "note": "Relative leukopenia with neutropenia — enteric fever pattern",
    },
    {
        "name": "Bacterial Infection",
        "criteria": {"wbc": "high", "neutrophils": "high"},
        "confidence_base": 0.80,
        "india_common": True,
        "note": "Neutrophilic leukocytosis — bacterial infection likely",
    },
    {
        "name": "Viral Infection Pattern",
        "criteria": {"wbc": "low", "lymphocytes": "high"},
        "confidence_base": 0.75,
        "india_common": True,
        "note": "Lymphocytosis with leukopenia — viral etiology likely",
    },
    {
        "name": "Eosinophilia (Parasitic)",
        "criteria": {"eosinophils": "high"},
        "confidence_base": 0.80,
        "india_common": True,
        "note": "Elevated eosinophils — intestinal parasites common in India, check stool for ova and cysts",
    },
    {
        "name": "Severe Thrombocytopenia",
        "criteria": {"platelets": "low"},
        "confidence_base": 0.90,
        "india_common": True,
        "note": "Platelet count critically low — bleeding risk, urgent review needed",
    },
    {
        "name": "Pancytopenia",
        "criteria": {"hemoglobin": "low", "wbc": "low", "platelets": "low"},
        "confidence_base": 0.90,
        "india_common": False,
        "note": "All three cell lines low — bone marrow pathology, urgent referral",
    },
    {
        "name": "Anemia of Chronic Disease",
        "criteria": {"hemoglobin": "low", "mcv": "normal_or_low", "rdw": "normal"},
        "confidence_base": 0.70,
        "india_common": True,
        "note": "Normocytic normochromic anemia — consider chronic infection or inflammatory condition",
    },
]

# ===========================================================================
# Groq client — lazily initialised
# ===========================================================================

_groq_client: AsyncGroq | None = None


def _get_groq() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY environment variable is not set")
        _groq_client = AsyncGroq(api_key=api_key)
    return _groq_client


# ===========================================================================
# Groq synthesis prompt
# ===========================================================================

_GROQ_PROMPT = """You are a hematology specialist AI for Indian patients.
Interpret this CBC report and provide clinical guidance.

Patient: PLACEHOLDER_AGEyr PLACEHOLDER_SEX
Known conditions: PLACEHOLDER_KNOWN_CONDITIONS

Parsed CBC Values:
PLACEHOLDER_PARSED_VALUES_JSON

Abnormal Findings:
PLACEHOLDER_ABNORMAL_FLAGS_JSON

Patterns Detected:
PLACEHOLDER_PATTERNS_JSON

Provide interpretation. Return ONLY valid JSON:
{
  "clinical_summary": "2-3 sentences overall",
  "primary_finding": "most important finding",
  "risk_level": "low|moderate|high|critical",
  "risk_reason": "why this risk level",
  "immediate_actions": [],
  "follow_up_tests": [
    {"test": "name", "reason": "why", "priority": "immediate|48h|week"}
  ],
  "india_context": "India-specific interpretation",
  "patient_explanation": "simple language for patient",
  "monitoring_needed": true or false
}"""


def _render_groq_prompt(
    age: int,
    sex: str,
    known_conditions: list[str],
    parsed: dict,
    flags: list[dict],
    patterns: list[dict],
) -> str:
    return (
        _GROQ_PROMPT
        .replace("PLACEHOLDER_AGE", str(age))
        .replace("PLACEHOLDER_SEX", sex)
        .replace("PLACEHOLDER_KNOWN_CONDITIONS", ", ".join(known_conditions) or "none")
        .replace("PLACEHOLDER_PARSED_VALUES_JSON", json.dumps(parsed, indent=2))
        .replace("PLACEHOLDER_ABNORMAL_FLAGS_JSON", json.dumps(flags, indent=2))
        .replace("PLACEHOLDER_PATTERNS_JSON", json.dumps(patterns, indent=2))
    )


# ===========================================================================
# Step 1 — range selection
# ===========================================================================


def select_ranges(age: int, sex: str) -> dict[str, tuple[float, float]]:
    if age < 12:
        return PEDIATRIC_RANGES
    if sex.lower() == "female":
        return FEMALE_RANGES
    return MALE_RANGES


# ===========================================================================
# Step 2 — regex parsing
# ===========================================================================


def parse_cbc(raw_text: str) -> dict[str, float]:
    """
    Extract CBC marker values from free-text lab reports.
    Strips Indian comma formatting (e.g. 1,10,000) before float conversion.
    Silently skips any value that cannot be parsed.
    """
    parsed: dict[str, float] = {}
    for marker, pattern in MARKER_PATTERNS.items():
        match = pattern.search(raw_text)
        if not match:
            continue
        value_str = match.group(1).replace(",", "")
        try:
            parsed[marker] = float(value_str)
        except ValueError:
            logger.debug("parse_cbc: could not convert %r to float for %s", value_str, marker)
    return parsed


# ===========================================================================
# Step 3 — abnormal flag detection
# ===========================================================================


def get_severity(
    deviation: float,
    marker: str,
    value: float,
    direction: str,
) -> str:
    """Return 'critical', 'moderate', or 'mild' for a given deviation."""
    if marker in CRITICAL_VALUES:
        thresholds = CRITICAL_VALUES[marker]
        if direction == "low" and value <= thresholds["low"]:
            return "critical"
        if direction == "high" and value >= thresholds["high"]:
            return "critical"
    if deviation > 0.50:
        return "critical"
    if deviation > 0.20:
        return "moderate"
    return "mild"


def flag_abnormals(
    parsed: dict[str, float],
    ranges: dict[str, tuple[float, float]],
) -> list[dict]:
    """Compare each parsed value against the patient's reference range."""
    flags: list[dict] = []
    for marker, value in parsed.items():
        if marker not in ranges:
            continue
        low, high = ranges[marker]
        if value < low:
            deviation = (low - value) / low
            severity = get_severity(deviation, marker, value, "low")
            flags.append({
                "marker":          marker,
                "value":           str(value),
                "reference_range": f"{low} - {high}",
                "direction":       "low",
                "severity":        severity,
                "interpretation":  f"{marker} is LOW at {value}",
            })
        elif value > high:
            deviation = (value - high) / high
            severity = get_severity(deviation, marker, value, "high")
            flags.append({
                "marker":          marker,
                "value":           str(value),
                "reference_range": f"{low} - {high}",
                "direction":       "high",
                "severity":        severity,
                "interpretation":  f"{marker} is HIGH at {value}",
            })
    return flags


# ===========================================================================
# Step 4 — pattern recognition
# ===========================================================================


def detect_patterns(
    parsed: dict[str, float],
    flags: list[dict],
    ranges: dict[str, tuple[float, float]],
) -> list[dict]:
    """
    Match parsed values against the PATTERNS library.
    Requires ≥66% of a pattern's criteria to be satisfied for a match.
    """
    flagged_low = {f["marker"] for f in flags if f["direction"] == "low"}
    flagged_high = {f["marker"] for f in flags if f["direction"] == "high"}
    flagged_any = flagged_low | flagged_high

    matched: list[dict] = []
    for pattern in PATTERNS:
        criteria_total = len(pattern["criteria"])
        if criteria_total == 0:
            continue
        criteria_met = 0

        for marker, condition in pattern["criteria"].items():
            if marker not in parsed:
                continue
            if condition == "low" and marker in flagged_low:
                criteria_met += 1
            elif condition == "high" and marker in flagged_high:
                criteria_met += 1
            elif condition == "normal_or_low" and marker not in flagged_high:
                criteria_met += 1
            elif condition == "normal" and marker not in flagged_any:
                criteria_met += 1

        match_ratio = criteria_met / criteria_total
        if match_ratio >= 0.66:
            confidence = round(pattern["confidence_base"] * match_ratio, 2)
            matched.append({
                "pattern":         pattern["name"],
                "confidence":      confidence,
                "india_common":    pattern["india_common"],
                "note":            pattern["note"],
                "criteria_matched": criteria_met,
                "criteria_total":  criteria_total,
            })

    return sorted(matched, key=lambda x: x["confidence"], reverse=True)


# ===========================================================================
# Step 5 — Groq synthesis
# ===========================================================================


async def _groq_synthesize(
    age: int,
    sex: str,
    known_conditions: list[str],
    parsed: dict,
    flags: list[dict],
    patterns: list[dict],
) -> dict | None:
    prompt = _render_groq_prompt(age, sex, known_conditions, parsed, flags, patterns)
    try:
        response = await _get_groq().chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Interpret this CBC report now."},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception:
        logger.exception("_groq_synthesize: Groq call or parse failed")
        return None


def _rule_based_risk(flags: list[dict]) -> str:
    """Derive a risk level from flags alone when Groq is unavailable."""
    severities = {f["severity"] for f in flags}
    if "critical" in severities:
        return "critical"
    if "moderate" in severities:
        return "high"
    if "mild" in severities:
        return "moderate"
    return "low"


def _fallback_result(
    parsed: dict,
    flags: list[dict],
    patterns: list[dict],
) -> dict:
    """Safe fallback when Groq is unreachable."""
    risk = _rule_based_risk(flags)
    primary = patterns[0]["pattern"] if patterns else (
        flags[0]["interpretation"] if flags else "No significant abnormalities detected"
    )
    return {
        "clinical_summary": f"CBC shows {len(flags)} abnormal finding(s). "
                            f"Pattern: {primary}.",
        "primary_finding":     primary,
        "risk_level":          risk,
        "risk_reason":         "Determined from abnormal flag severity",
        "immediate_actions":   [],
        "follow_up_tests":     [],
        "india_context":       "Groq synthesis unavailable — rule-based assessment only",
        "patient_explanation": "Some blood test values are outside normal range. "
                               "Please consult your doctor for full explanation.",
        "monitoring_needed":   risk in ("high", "critical"),
    }


# ===========================================================================
# Main interpreter function
# ===========================================================================


async def interpret_cbc(inputs: dict) -> dict:
    """
    Full CBC interpretation pipeline:
    parse → flag → pattern match → Groq synthesis → structured result.
    """
    raw_text: str = inputs.get("raw_text", "")
    age: int = int(inputs.get("patient_age", 30))
    sex: str = str(inputs.get("patient_sex", "male"))
    known_conditions: list[str] = inputs.get("known_conditions", [])

    logger.info(
        "interpret_cbc | age=%d | sex=%s | conditions=%d | text_len=%d",
        age, sex, len(known_conditions), len(raw_text),
    )

    ranges = select_ranges(age, sex)

    # Steps 2–4 — pure Python, never raise
    parsed = parse_cbc(raw_text)
    flags = flag_abnormals(parsed, ranges)
    patterns = detect_patterns(parsed, flags, ranges)

    logger.info(
        "interpret_cbc | parsed=%d markers | flags=%d | patterns=%d",
        len(parsed), len(flags), len(patterns),
    )

    # Step 5 — Groq synthesis (optional)
    groq_result = await _groq_synthesize(age, sex, known_conditions, parsed, flags, patterns)
    synthesis = groq_result if groq_result else _fallback_result(parsed, flags, patterns)

    primary_pattern = patterns[0]["pattern"] if patterns else None

    result = {
        "report_type":       "CBC",
        "parsed_values":     parsed,
        "values_count":      len(parsed),
        "abnormal_flags":    flags,
        "abnormal_count":    len(flags),
        "patterns_detected": patterns,
        "primary_pattern":   primary_pattern,
        "risk_level":        synthesis.get("risk_level", "low"),
        "risk_reason":       synthesis.get("risk_reason", ""),
        "immediate_actions": synthesis.get("immediate_actions", []),
        "follow_up_tests":   synthesis.get("follow_up_tests", []),
        "clinical_summary":  synthesis.get("clinical_summary", ""),
        "primary_finding":   synthesis.get("primary_finding", ""),
        "india_context":     synthesis.get("india_context", ""),
        "patient_explanation": synthesis.get("patient_explanation", ""),
        "monitoring_needed": bool(synthesis.get("monitoring_needed", False)),
    }

    logger.info(
        "interpret_cbc OK | risk=%s | pattern=%s | groq=%s",
        result["risk_level"],
        primary_pattern or "none",
        "yes" if groq_result else "fallback",
    )
    return result
