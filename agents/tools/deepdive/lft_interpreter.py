"""
ClinIQ 2.0 — LFT (Liver Function Test) DeepDive interpreter.

Three-layer interpretation matching the CBC structure:
  1. Regex parsing   — handles all common Indian lab abbreviations
  2. Rule engine     — flags abnormals, applies India-specific LFT
     pattern recognition, and adds ATT hepatotoxicity warnings for
     patients known to be on tuberculosis treatment
  3. Groq synthesis  — hepatology specialist prompt with critical
     India context (Hep A/B/E prevalence, ATT drugs, malnutrition)

Called from agents/tools/deepdive/__init__.py.
"""

import json
import logging
import os
import re
from typing import Any

from backend.llm.router import llm_chat

logger = logging.getLogger("cliniq.tools.deepdive.lft")

_ATT_WARNING = (
    "⚠️ Patient is on ATT drugs (rifampicin/isoniazid/pyrazinamide) — "
    "this elevation may represent drug-induced hepatotoxicity. "
    "Consider stopping ATT and urgent hepatology review."
)

# ===========================================================================
# Reference ranges — (low, high) inclusive
# ===========================================================================

LFT_RANGES: dict[str, tuple[float, float]] = {
    "total_bilirubin":      (0.2,  1.2),
    "direct_bilirubin":     (0.0,  0.3),
    "indirect_bilirubin":   (0.2,  0.9),
    "sgot_ast":             (10.0, 40.0),
    "sgpt_alt":             (7.0,  56.0),
    "alkaline_phosphatase": (44.0, 147.0),
    "ggt":                  (8.0,  61.0),
    "total_protein":        (6.0,  8.3),
    "albumin":              (3.5,  5.0),
    "globulin":             (2.0,  3.5),
    "ag_ratio":             (1.2,  2.2),
    "pt_inr":               (0.8,  1.2),
}

# GGT reference differs for females
GGT_FEMALE_RANGE: tuple[float, float] = (5.0, 36.0)

CRITICAL_LFT: dict[str, dict[str, float]] = {
    "sgpt_alt":        {"high": 1000.0},
    "sgot_ast":        {"high": 1000.0},
    "total_bilirubin": {"high": 15.0},
    "pt_inr":          {"high": 2.5},
    "albumin":         {"low":  2.0},
}

# ===========================================================================
# Compiled regex patterns — module-level
# ===========================================================================

LFT_PATTERNS: dict[str, re.Pattern] = {
    "total_bilirubin": re.compile(
        r"(?:total\s*bilirubin|s\.?\s*bilirubin\s*total|t\.?\s*bil)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "direct_bilirubin": re.compile(
        r"(?:direct\s*bilirubin|d\.?\s*bil|conjugated)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "indirect_bilirubin": re.compile(
        r"(?:indirect\s*bilirubin|i\.?\s*bil|unconjugated)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "sgot_ast": re.compile(
        r"(?:sgot|ast|aspartate)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "sgpt_alt": re.compile(
        r"(?:sgpt|alt|alanine)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "alkaline_phosphatase": re.compile(
        r"(?:alkaline\s*phosphatase|alk\.?\s*phos|alp)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "ggt": re.compile(
        r"(?:ggt|gamma\s*gt|gamma\s*glutamyl)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "total_protein": re.compile(
        r"(?:total\s*protein|s\.?\s*protein)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "albumin": re.compile(
        r"(?:albumin|s\.?\s*albumin)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "globulin": re.compile(
        r"globulin\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "ag_ratio": re.compile(
        r"(?:a\s*[/\\]\s*g\s*ratio|ag\s*ratio)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    "pt_inr": re.compile(
        r"(?:pt\s*inr|inr|prothrombin)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
}

# ===========================================================================
# LFT clinical pattern library
# ===========================================================================

LFT_CLINICAL_PATTERNS: list[dict[str, Any]] = [
    {
        "name": "Acute Hepatitis",
        "criteria": {"sgpt_alt": "very_high"},
        "threshold": {"sgpt_alt": 10},      # >10× ULN
        "confidence_base": 0.90,
        "india_common": True,
        "note": "SGPT >10× ULN — acute hepatitis. In India: Hepatitis A, B, E most common. Drug-induced (ATT drugs) also common.",
    },
    {
        "name": "Obstructive Jaundice",
        "criteria": {
            "total_bilirubin":      "high",
            "direct_bilirubin":     "high",
            "alkaline_phosphatase": "high",
        },
        "confidence_base": 0.85,
        "india_common": True,
        "note": "Cholestatic pattern — gallstones, biliary obstruction, or pancreatic cause likely",
    },
    {
        "name": "Hemolytic Jaundice",
        "criteria": {
            "total_bilirubin":    "high",
            "indirect_bilirubin": "high",
        },
        "confidence_base": 0.80,
        "india_common": True,
        "note": "Pre-hepatic jaundice — malaria hemolysis, G6PD deficiency, sickle cell common in India",
    },
    {
        "name": "Alcoholic Hepatitis",
        "criteria": {
            "sgot_ast": "high",
            "ggt":      "high",
        },
        "ratio_check": {"sgot_ast/sgpt_alt": 2.0},   # AST:ALT ≥ 2
        "confidence_base": 0.75,
        "india_common": True,
        "note": "AST:ALT ratio >2 with elevated GGT — alcoholic liver disease pattern",
    },
    {
        "name": "Non-Alcoholic Fatty Liver (NAFLD)",
        "criteria": {
            "sgpt_alt": "mild_high",
            "sgot_ast": "mild_high",
        },
        "threshold": {"sgpt_alt_max": 3, "sgot_ast_max": 3},   # <3× ULN
        "confidence_base": 0.70,
        "india_common": True,
        "note": "Mild transaminase elevation — NAFLD rapidly increasing in urban India",
    },
    {
        "name": "ATT Drug-Induced Hepatotoxicity",
        "criteria": {
            "sgpt_alt":        "high",
            "total_bilirubin": "high",
        },
        "confidence_base": 0.80,
        "india_common": True,
        "note": "If patient on TB drugs (rifampicin, isoniazid, pyrazinamide) — STOP ATT immediately, urgent review",
    },
    {
        "name": "Liver Synthetic Dysfunction",
        "criteria": {
            "albumin": "low",
            "pt_inr":  "high",
        },
        "confidence_base": 0.90,
        "india_common": False,
        "note": "Low albumin + high INR — severe liver dysfunction, urgent hepatology referral needed",
    },
    {
        "name": "Hypoalbuminemia",
        "criteria": {"albumin": "low"},
        "confidence_base": 0.85,
        "india_common": True,
        "note": "Low albumin — malnutrition very common in India, also consider nephrotic syndrome or chronic liver disease",
    },
]

# ===========================================================================
# Groq synthesis prompt
# ===========================================================================

_GROQ_PROMPT = """You are a hepatology specialist AI for Indian patients.

Critical India context:
- Hepatitis A and E: feco-oral transmission, common in monsoon, often self-limiting
- Hepatitis B: 4% prevalence in India, check HBsAg if acute hepatitis pattern
- Alcoholic liver disease: common in adult males
- ATT hepatotoxicity: if patient on TB drugs and LFT abnormal, this is an emergency
- Malnutrition: low albumin very common, not always liver disease
- Jaundice in pregnancy: rule out HELLP, acute fatty liver
- Wilson's disease: young patient + liver + neurological symptoms

Patient: PLACEHOLDER_AGEyr PLACEHOLDER_SEX
Known conditions: PLACEHOLDER_KNOWN_CONDITIONS
LFT Values: PLACEHOLDER_PARSED_VALUES
Abnormal Findings: PLACEHOLDER_ABNORMAL_FLAGS
Patterns: PLACEHOLDER_PATTERNS

Return ONLY valid JSON, no markdown:
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
        .replace("PLACEHOLDER_PARSED_VALUES", json.dumps(parsed, indent=2))
        .replace("PLACEHOLDER_ABNORMAL_FLAGS", json.dumps(flags, indent=2))
        .replace("PLACEHOLDER_PATTERNS", json.dumps(patterns, indent=2))
    )


# ===========================================================================
# Groq client — lazily initialised
# ===========================================================================

# ===========================================================================
# Helpers
# ===========================================================================


def _is_att_patient(known_conditions: list[str]) -> bool:
    """Return True if the patient is likely on anti-tuberculosis therapy."""
    for cond in known_conditions:
        lc = cond.lower().strip()
        if "tuberculosis" in lc or lc == "tb" or lc.startswith("tb ") or " tb" in lc:
            return True
    return False


def _effective_ranges(sex: str) -> dict[str, tuple[float, float]]:
    """Return LFT_RANGES with GGT adjusted for sex."""
    ranges = dict(LFT_RANGES)
    if sex.lower() == "female":
        ranges["ggt"] = GGT_FEMALE_RANGE
    return ranges


# ===========================================================================
# Step 2 — regex parsing
# ===========================================================================


def parse_lft(raw_text: str) -> dict[str, float]:
    """Extract LFT values from raw report text, skipping unparseable entries."""
    parsed: dict[str, float] = {}
    for marker, pattern in LFT_PATTERNS.items():
        match = pattern.search(raw_text)
        if not match:
            continue
        value_str = match.group(1).replace(",", "")
        try:
            parsed[marker] = float(value_str)
        except ValueError:
            logger.debug("parse_lft: could not convert %r to float for %s", value_str, marker)
    return parsed


# ===========================================================================
# Step 3 — abnormal flag detection
# ===========================================================================


def _get_lft_severity(
    marker: str,
    value: float,
    direction: str,
    deviation: float,
) -> str:
    if marker in CRITICAL_LFT:
        thresholds = CRITICAL_LFT[marker]
        if direction == "low" and "low" in thresholds and value <= thresholds["low"]:
            return "critical"
        if direction == "high" and "high" in thresholds and value >= thresholds["high"]:
            return "critical"
    if deviation > 0.50:
        return "critical"
    if deviation > 0.20:
        return "moderate"
    return "mild"


def flag_lft_abnormals(
    parsed: dict[str, float],
    ranges: dict[str, tuple[float, float]],
    known_conditions: list[str],
) -> list[dict]:
    """
    Flag out-of-range LFT values.  Appends an ATT hepatotoxicity warning to
    every liver-enzyme flag when the patient is on tuberculosis treatment.
    """
    att_patient = _is_att_patient(known_conditions)
    flags: list[dict] = []

    for marker, value in parsed.items():
        if marker not in ranges:
            continue
        low, high = ranges[marker]
        flag: dict | None = None

        if value < low:
            deviation = (low - value) / low
            severity = _get_lft_severity(marker, value, "low", deviation)
            flag = {
                "marker":          marker,
                "value":           str(value),
                "reference_range": f"{low} - {high}",
                "direction":       "low",
                "severity":        severity,
                "interpretation":  f"{marker} is LOW at {value}",
            }
        elif value > high:
            deviation = (value - high) / high
            severity = _get_lft_severity(marker, value, "high", deviation)
            flag = {
                "marker":          marker,
                "value":           str(value),
                "reference_range": f"{low} - {high}",
                "direction":       "high",
                "severity":        severity,
                "interpretation":  f"{marker} is HIGH at {value}",
            }

        if flag is not None:
            if att_patient and marker in ("sgot_ast", "sgpt_alt", "total_bilirubin", "alkaline_phosphatase"):
                flag["att_warning"] = _ATT_WARNING
            flags.append(flag)

    return flags


# ===========================================================================
# Step 4 — pattern detection
# ===========================================================================


def detect_lft_patterns(
    parsed: dict[str, float],
    flags: list[dict],
    known_conditions: list[str],
) -> list[dict]:
    """
    Match parsed LFT values against the clinical pattern library.
    Handles 'very_high' (>N× ULN), 'mild_high' (<N× ULN), and
    ratio checks (AST:ALT) in addition to plain high/low criteria.
    """
    flagged_low = {f["marker"] for f in flags if f["direction"] == "low"}
    flagged_high = {f["marker"] for f in flags if f["direction"] == "high"}
    att_patient = _is_att_patient(known_conditions)

    matched: list[dict] = []

    for pattern in LFT_CLINICAL_PATTERNS:
        criteria_total = len(pattern["criteria"])
        criteria_met = 0

        for marker, condition in pattern["criteria"].items():
            if marker not in parsed:
                continue
            value = parsed[marker]
            uln = LFT_RANGES[marker][1] if marker in LFT_RANGES else None
            lln = LFT_RANGES[marker][0] if marker in LFT_RANGES else None

            if condition == "high" and marker in flagged_high:
                criteria_met += 1

            elif condition == "low" and marker in flagged_low:
                criteria_met += 1

            elif condition == "very_high":
                # Must be high AND exceed the specified multiple of ULN
                if marker in flagged_high and uln:
                    multiplier = pattern.get("threshold", {}).get(marker)
                    if multiplier and value > multiplier * uln:
                        criteria_met += 1
                    elif not multiplier:
                        criteria_met += 1   # no threshold key = any elevation counts

            elif condition == "mild_high":
                # Must be high BUT below the max multiplier of ULN
                if marker in flagged_high and uln:
                    max_key = f"{marker}_max"
                    max_mult = pattern.get("threshold", {}).get(max_key)
                    if max_mult and value < max_mult * uln:
                        criteria_met += 1
                    elif not max_mult:
                        criteria_met += 1

        # Ratio check — added as an extra computable criterion
        if "ratio_check" in pattern:
            for ratio_key, ratio_threshold in pattern["ratio_check"].items():
                parts = ratio_key.split("/")
                if len(parts) == 2:
                    num_m, denom_m = parts
                    if num_m in parsed and denom_m in parsed and parsed[denom_m] > 0:
                        criteria_total += 1
                        if (parsed[num_m] / parsed[denom_m]) >= ratio_threshold:
                            criteria_met += 1

        if criteria_total == 0:
            continue
        match_ratio = criteria_met / criteria_total
        if match_ratio < 0.66:
            continue

        note = pattern["note"]
        # Elevate ATT warning on all non-ATT-specific patterns when patient is on ATT
        if att_patient and "ATT" not in pattern["name"]:
            note += " | ⚠️ Patient is on ATT — consider ATT hepatotoxicity as co-contributor."

        matched.append({
            "pattern":          pattern["name"],
            "confidence":       round(pattern["confidence_base"] * match_ratio, 2),
            "india_common":     pattern["india_common"],
            "note":             note,
            "criteria_matched": criteria_met,
            "criteria_total":   criteria_total,
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
        raw = (await llm_chat(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Interpret this LFT report now."},
            ],
            temperature=0.1,
            max_tokens=1024,
        )).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception:
        logger.exception("_groq_synthesize: Groq call or parse failed")
        return None


def _rule_based_risk(flags: list[dict]) -> str:
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
    risk = _rule_based_risk(flags)
    primary = (
        patterns[0]["pattern"]
        if patterns
        else (flags[0]["interpretation"] if flags else "No significant abnormalities detected")
    )
    return {
        "clinical_summary":    f"LFT shows {len(flags)} abnormal finding(s). Pattern: {primary}.",
        "primary_finding":     primary,
        "risk_level":          risk,
        "risk_reason":         "Determined from abnormal flag severity",
        "immediate_actions":   [],
        "follow_up_tests":     [],
        "india_context":       "Groq synthesis unavailable — rule-based assessment only",
        "patient_explanation": "Some liver test values are outside normal range. "
                               "Please consult your doctor.",
        "monitoring_needed":   risk in ("high", "critical"),
    }


# ===========================================================================
# Main interpreter function
# ===========================================================================


async def interpret_lft(inputs: dict) -> dict:
    """
    Full LFT interpretation: parse → flag (with ATT annotation) →
    pattern match → Groq hepatology synthesis → structured result.
    """
    raw_text: str = inputs.get("raw_text", "")
    age: int = int(inputs.get("patient_age", 30))
    sex: str = str(inputs.get("patient_sex", "male"))
    known_conditions: list[str] = inputs.get("known_conditions", [])

    logger.info(
        "interpret_lft | age=%d | sex=%s | att=%s | text_len=%d",
        age, sex, _is_att_patient(known_conditions), len(raw_text),
    )

    ranges = _effective_ranges(sex)

    parsed = parse_lft(raw_text)
    flags = flag_lft_abnormals(parsed, ranges, known_conditions)
    patterns = detect_lft_patterns(parsed, flags, known_conditions)

    logger.info(
        "interpret_lft | parsed=%d markers | flags=%d | patterns=%d",
        len(parsed), len(flags), len(patterns),
    )

    groq_result = await _groq_synthesize(age, sex, known_conditions, parsed, flags, patterns)
    synthesis = groq_result if groq_result else _fallback_result(parsed, flags, patterns)

    primary_pattern = patterns[0]["pattern"] if patterns else None

    result = {
        "report_type":         "LFT",
        "parsed_values":       parsed,
        "values_count":        len(parsed),
        "abnormal_flags":      flags,
        "abnormal_count":      len(flags),
        "patterns_detected":   patterns,
        "primary_pattern":     primary_pattern,
        "risk_level":          synthesis.get("risk_level", "low"),
        "risk_reason":         synthesis.get("risk_reason", ""),
        "immediate_actions":   synthesis.get("immediate_actions", []),
        "follow_up_tests":     synthesis.get("follow_up_tests", []),
        "clinical_summary":    synthesis.get("clinical_summary", ""),
        "primary_finding":     synthesis.get("primary_finding", ""),
        "india_context":       synthesis.get("india_context", ""),
        "patient_explanation": synthesis.get("patient_explanation", ""),
        "monitoring_needed":   bool(synthesis.get("monitoring_needed", False)),
    }

    logger.info(
        "interpret_lft OK | risk=%s | pattern=%s | groq=%s",
        result["risk_level"],
        primary_pattern or "none",
        "yes" if groq_result else "fallback",
    )
    return result
