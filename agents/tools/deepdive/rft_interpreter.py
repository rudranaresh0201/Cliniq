"""
ClinIQ 2.0 — RFT (Renal Function Test) DeepDive interpreter.

Three-layer interpretation matching the CBC and LFT structure:
  1. Regex parsing   — 12 patterns, handles Indian lab formats
                       (serum creatinine, blood urea, s.sodium, etc.)
  2. Rule engine     — CKD staging, critical value escalation thresholds,
                       10 India-tuned clinical pattern detectors;
                       cross-checks medications for pyrazinamide (ATT
                       nephrotoxicity) and diagnosis hypotheses for Dengue
  3. Groq synthesis  — nephrology specialist prompt with India-specific
                       context (DM/HTN-driven CKD, Jan Aushadhi drug list,
                       Dengue-AKI, snake bite nephropathy, NSAID overuse)

Called from agents/tools/deepdive/__init__.py.
"""

import json
import logging
import os
import re
from typing import Any

from groq import AsyncGroq

logger = logging.getLogger("cliniq.tools.deepdive.rft")

_GROQ_MODEL = "llama-3.3-70b-versatile"

# ---------------------------------------------------------------------------
# Warning strings injected onto relevant flags
# ---------------------------------------------------------------------------

_ATT_NEPHRO_WARNING = (
    "⚠️ Patient on pyrazinamide (ATT) — pyrazinamide competitively inhibits "
    "renal tubular urate secretion, causing hyperuricaemia and gout risk. "
    "Also monitor creatinine for direct tubular toxicity. "
    "Consult TB physician before dose adjustment."
)

_DENGUE_AKI_WARNING = (
    "⚠️ Dengue in differential — Dengue-associated AKI common in India during "
    "monsoon; usually oliguric and reversible. Avoid NSAIDs and nephrotoxins. "
    "Monitor urine output closely; platelet trend also relevant."
)

_CRITICAL_K_WARNING = (
    "🚨 CRITICAL HYPERKALEMIA — K ≥6.5 mEq/L: risk of lethal cardiac arrhythmia. "
    "Immediate ECG, IV calcium gluconate 10 mL, salbutamol nebulisation, "
    "and nephrology review required. Do NOT delay."
)

# ===========================================================================
# Reference ranges — (low, high) inclusive
# ===========================================================================

ADULT_MALE_RANGES: dict[str, tuple[float, float]] = {
    "creatinine":           (0.7,   1.2),    # mg/dL
    "urea":                 (15.0,  40.0),   # mg/dL  (Blood Urea — Indian convention)
    "bun":                  (7.0,   20.0),   # mg/dL  (BUN — used in some private labs)
    "uric_acid":            (3.5,   7.2),    # mg/dL
    "egfr":                 (90.0,  200.0),  # mL/min/1.73m² (200 = sentinel upper)
    "sodium":               (136.0, 145.0),  # mEq/L
    "potassium":            (3.5,   5.0),    # mEq/L
    "chloride":             (98.0,  107.0),  # mEq/L
    "bicarbonate":          (22.0,  29.0),   # mEq/L
    "calcium":              (8.5,   10.5),   # mg/dL
    "phosphorus":           (2.5,   4.5),    # mg/dL
    "creatinine_clearance": (85.0,  125.0),  # mL/min
}

ADULT_FEMALE_RANGES: dict[str, tuple[float, float]] = {
    "creatinine":           (0.5,   1.1),
    "urea":                 (15.0,  40.0),
    "bun":                  (7.0,   20.0),
    "uric_acid":            (2.6,   6.0),    # lower in females
    "egfr":                 (90.0,  200.0),
    "sodium":               (136.0, 145.0),
    "potassium":            (3.5,   5.0),
    "chloride":             (98.0,  107.0),
    "bicarbonate":          (22.0,  29.0),
    "calcium":              (8.5,   10.5),
    "phosphorus":           (2.5,   4.5),
    "creatinine_clearance": (75.0,  115.0),
}

PEDIATRIC_RANGES: dict[str, tuple[float, float]] = {
    "creatinine":           (0.3,   0.7),
    "urea":                 (10.0,  30.0),
    "bun":                  (5.0,   18.0),
    "uric_acid":            (2.0,   5.5),
    "egfr":                 (90.0,  200.0),
    "sodium":               (136.0, 145.0),
    "potassium":            (3.4,   4.7),
    "chloride":             (98.0,  107.0),
    "bicarbonate":          (20.0,  28.0),
    "calcium":              (8.8,   10.8),
    "phosphorus":           (4.0,   6.0),    # higher in children
    "creatinine_clearance": (70.0,  110.0),
}

# ---------------------------------------------------------------------------
# CKD staging by eGFR (KDIGO 2012)
# ---------------------------------------------------------------------------

# Each entry: (label, egfr_low_inclusive, egfr_high_exclusive | None)
_CKD_STAGES: list[tuple[str, float, float | None]] = [
    ("G5 — Kidney Failure (<15 mL/min)",          0.0,   15.0),
    ("G4 — Severely Decreased (15–29 mL/min)",    15.0,  30.0),
    ("G3b — Mod–Severely Decreased (30–44)",      30.0,  45.0),
    ("G3a — Mildly–Moderately Decreased (45–59)", 45.0,  60.0),
    ("G2 — Mildly Decreased (60–89)",             60.0,  90.0),
    ("G1 — Normal or High (≥90)",                 90.0,  None),
]


def ckd_stage(egfr: float) -> str:
    for label, low, high in _CKD_STAGES:
        if high is None and egfr >= low:
            return label
        if high is not None and low <= egfr < high:
            return label
    return "Unknown"


# ---------------------------------------------------------------------------
# Critical value thresholds — any breach triggers immediate escalation
# ---------------------------------------------------------------------------

CRITICAL_RFT: dict[str, dict[str, float]] = {
    "creatinine":  {"high": 10.0},
    "potassium":   {"low": 2.5,   "high": 6.5},
    "sodium":      {"low": 120.0, "high": 160.0},
    "bicarbonate": {"low": 10.0},
    "calcium":     {"low": 6.5,   "high": 13.0},
    "egfr":        {"low": 15.0},   # G5 CKD
}

# Moderate hyperkalemia threshold — warn before hitting the critical ceiling
_K_WARN = 5.5   # K > 5.5 → severity = moderate regardless of deviation

# ===========================================================================
# Compiled regex patterns — module-level (zero recompilation cost)
# ===========================================================================

RFT_MARKER_PATTERNS: dict[str, re.Pattern] = {
    # 1. Creatinine
    "creatinine": re.compile(
        r"(?:serum\s+creatinine|s\.?\s*creatinine|creatinine(?:\s+serum)?|creat)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    # 2. Blood Urea (Indian convention — urea molecule, not nitrogen fraction)
    "urea": re.compile(
        r"(?:blood\s+urea(?!\s+nitro)|urea\s*(?:blood|serum)?(?!\s+nitro))\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    # 3. BUN — used in some Indian private labs and US-format reports
    "bun": re.compile(
        r"(?:blood\s+urea\s+nitrogen|b\.?u\.?n\.?)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    # 4. Uric acid
    "uric_acid": re.compile(
        r"(?:uric\s+acid|s\.?\s*uric\s*acid|serum\s+uric\s+acid)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    # 5. eGFR
    "egfr": re.compile(
        r"(?:e\.?g\.?f\.?r\.?|estimated\s*gfr|e\s*-\s*gfr|glomerular\s+filtration\s+rate)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    # 6. Sodium
    "sodium": re.compile(
        r"(?:serum\s+sodium|s\.?\s*sodium|sodium)\s*[:\-]?\s*([\d.]+)(?!\s*%)",
        re.IGNORECASE,
    ),
    # 7. Potassium
    "potassium": re.compile(
        r"(?:serum\s+potassium|s\.?\s*potassium|potassium)\s*[:\-]?\s*([\d.]+)(?!\s*%)",
        re.IGNORECASE,
    ),
    # 8. Chloride
    "chloride": re.compile(
        r"(?:serum\s+chloride|s\.?\s*chloride|chloride)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    # 9. Bicarbonate / CO₂
    "bicarbonate": re.compile(
        r"(?:bicarbonate|hco\s*3|co\s*2\s*(?:content|bicarbonate)?|serum\s+co\s*2)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    # 10. Calcium
    "calcium": re.compile(
        r"(?:serum\s+calcium|s\.?\s*calcium|calcium\s+serum|calcium)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    # 11. Phosphorus / Phosphate
    "phosphorus": re.compile(
        r"(?:inorganic\s+phosph(?:orus|ate)|s\.?\s*phosph(?:orus|ate)|phosph(?:orus|ate))\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
    # 12. Creatinine clearance (24 h urine or calculated)
    "creatinine_clearance": re.compile(
        r"(?:creatinine\s+clearance|cr(?:eat)?\s*cl|c\.?c\.?r\.?)\s*[:\-]?\s*([\d.]+)",
        re.IGNORECASE,
    ),
}

# ===========================================================================
# Clinical pattern library — India-tuned, ordered by clinical priority
# ===========================================================================

RFT_PATTERNS: list[dict[str, Any]] = [
    {
        "name": "Acute Kidney Injury (AKI)",
        "criteria": {
            "creatinine": "high",
            "urea":       "high",
        },
        "confidence_base": 0.85,
        "india_common": True,
        "note": (
            "Elevated creatinine + urea — AKI pattern. "
            "Common India-specific causes: dehydration, sepsis, NSAID overuse, "
            "Dengue-AKI, ATT drugs, Russell's viper envenomation, contrast nephropathy. "
            "Classify as pre-renal / intrinsic / post-renal; check urine output."
        ),
    },
    {
        "name": "Chronic Kidney Disease (CKD)",
        "criteria": {
            "creatinine": "high",
            "egfr":       "low",
        },
        "confidence_base": 0.85,
        "india_common": True,
        "note": (
            "Elevated creatinine + reduced eGFR — CKD. "
            "Diabetes and hypertension are the leading causes in India. "
            "Check urine ACR, BP control (<130/80), restrict dietary protein/potassium. "
            "Jan Aushadhi: enalapril, losartan, amlodipine widely available."
        ),
    },
    {
        "name": "Pre-renal Azotemia",
        "criteria": {
            "urea":       "high",
            "creatinine": "high",
        },
        "ratio_check": {"urea/creatinine": 40.0},   # Blood Urea:Creatinine >40 (Indian units)
        "confidence_base": 0.80,
        "india_common": True,
        "note": (
            "Disproportionate urea elevation (blood urea:creatinine >40) — "
            "pre-renal cause likely: dehydration, poor oral intake, GI bleed, "
            "reduced cardiac output. IV/oral rehydration usually normalises values. "
            "Also consider high dietary protein."
        ),
    },
    {
        "name": "Hyperkalemia",
        "criteria": {"potassium": "high"},
        "confidence_base": 0.90,
        "india_common": True,
        "note": (
            "Elevated potassium — causes: CKD, ACE inhibitor / ARB use, "
            "Addison's disease, metabolic acidosis, massive haemolysis, "
            "haemolysed sample (artefact — repeat if no ECG changes). "
            "K >5.5 needs close monitoring; K >6.5 is a cardiac emergency."
        ),
    },
    {
        "name": "Hyponatremia",
        "criteria": {"sodium": "low"},
        "confidence_base": 0.90,
        "india_common": True,
        "note": (
            "Low serum sodium — evaluate volume status: "
            "hypovolaemic (diarrhoea, vomiting, burns), euvolaemic (SIADH, hypothyroidism), "
            "or hypervolaemic (heart failure, cirrhosis, nephrotic syndrome). "
            "Correct slowly (<8–10 mEq/L per 24 h) to prevent osmotic demyelination."
        ),
    },
    {
        "name": "Hypernatremia",
        "criteria": {"sodium": "high"},
        "confidence_base": 0.85,
        "india_common": True,
        "note": (
            "High serum sodium — almost always reflects free-water deficit "
            "(severe dehydration, inadequate oral intake, diabetes insipidus). "
            "Urgent free-water replacement; correct slowly to prevent cerebral oedema. "
            "Common in elderly, infants, and ICU patients."
        ),
    },
    {
        "name": "Dengue-associated AKI",
        "criteria": {
            "creatinine": "high",
            "urea":       "high",
        },
        "dengue_context": True,   # gate: only match if dengue in differential
        "confidence_base": 0.85,
        "india_common": True,
        "note": (
            "⚠️ Dengue in differential + elevated creatinine/urea — "
            "Dengue-AKI is common in India, especially in monsoon. "
            "Usually oliguric and reversible with supportive care. "
            "Strictly avoid NSAIDs; careful fluid balance; monitor platelet trend."
        ),
    },
    {
        "name": "ATT Nephrotoxicity / Pyrazinamide Hyperuricaemia",
        "criteria": {"uric_acid": "high"},
        "att_medication": True,   # gate: only match if on pyrazinamide
        "confidence_base": 0.85,
        "india_common": True,
        "note": (
            "⚠️ Pyrazinamide in medications + elevated uric acid — "
            "PZA inhibits renal tubular urate secretion. "
            "Risk of gouty arthritis and urate nephropathy. "
            "Discuss dose reduction with TB physician; allopurinol available in Jan Aushadhi. "
            "Also monitor creatinine for direct tubular toxicity (streptomycin)."
        ),
    },
    {
        "name": "Metabolic Acidosis",
        "criteria": {"bicarbonate": "low"},
        "confidence_base": 0.85,
        "india_common": True,
        "note": (
            "Low bicarbonate — metabolic acidosis. "
            "In CKD context: uraemic acidosis (most common). "
            "Other causes: DKA, severe diarrhoea, lactic acidosis, RTA. "
            "HCO₃ <10 mEq/L: urgent IV bicarbonate; HCO₃ 10–18: oral supplementation. "
            "Sodium bicarbonate tablets available in Jan Aushadhi."
        ),
    },
    {
        "name": "Hyperphosphatemia with CKD",
        "criteria": {
            "phosphorus":  "high",
            "creatinine":  "high",
        },
        "confidence_base": 0.80,
        "india_common": True,
        "note": (
            "Elevated phosphate + elevated creatinine — CKD-mineral bone disorder (CKD-MBD). "
            "Calcium × phosphorus product elevation increases vascular calcification risk. "
            "Dietary phosphate restriction and phosphate binders needed. "
            "Jan Aushadhi: calcium carbonate available; sevelamer at referral centres."
        ),
    },
]

# ===========================================================================
# Groq synthesis prompt
# ===========================================================================

_GROQ_PROMPT = """You are a nephrology specialist AI for Indian patients.

Critical India context for RFT interpretation:
- Diabetic nephropathy: #1 cause of CKD in India (T2DM epidemic, often late presentation)
- Hypertensive nephrosclerosis: #2 cause; many patients unaware of hypertension
- IgA nephropathy: most common primary GN in India; young adults, haematuria after URTI
- Dengue-AKI: very common in monsoon; usually reversible; strict avoid NSAIDs
- ATT nephrotoxicity: pyrazinamide → hyperuricaemia; streptomycin → tubular toxicity
- Russell's viper bite: direct nephrotoxin, common cause of AKI in rural India
- NSAID overuse: leading preventable cause of AKI/CKD worsening; cheap, OTC access
- Post-streptococcal GN: children, 2–4 weeks after sore throat; oedema, haematuria
- Contrast nephropathy: rising with CT scan use; pre-hydrate with IV normal saline
- Jan Aushadhi availability: enalapril, losartan, amlodipine, furosemide, torsemide,
  spironolactone, calcium carbonate, sodium bicarbonate, allopurinol, iron (oral), EPO

Patient: PLACEHOLDER_AGEyr PLACEHOLDER_SEX
Known conditions: PLACEHOLDER_CONDITIONS
Current medications: PLACEHOLDER_MEDICATIONS
Diagnosis hypotheses: PLACEHOLDER_HYPOTHESES
CKD Stage (eGFR-based): PLACEHOLDER_CKD_STAGE

RFT Values:
PLACEHOLDER_PARSED_VALUES

Abnormal Findings:
PLACEHOLDER_FLAGS

Patterns Detected:
PLACEHOLDER_PATTERNS

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
    current_medications: list[str],
    diagnosis_hypotheses: list[str],
    parsed: dict,
    flags: list[dict],
    patterns: list[dict],
    ckd_stage_str: str,
) -> str:
    return (
        _GROQ_PROMPT
        .replace("PLACEHOLDER_AGE",          str(age))
        .replace("PLACEHOLDER_SEX",          sex)
        .replace("PLACEHOLDER_CONDITIONS",   ", ".join(known_conditions) or "none")
        .replace("PLACEHOLDER_MEDICATIONS",  ", ".join(current_medications) or "none")
        .replace("PLACEHOLDER_HYPOTHESES",   ", ".join(diagnosis_hypotheses) or "none")
        .replace("PLACEHOLDER_CKD_STAGE",    ckd_stage_str)
        .replace("PLACEHOLDER_PARSED_VALUES", json.dumps(parsed, indent=2))
        .replace("PLACEHOLDER_FLAGS",        json.dumps(flags, indent=2))
        .replace("PLACEHOLDER_PATTERNS",     json.dumps(patterns, indent=2))
    )


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
# Context helpers
# ===========================================================================


def _is_on_pyrazinamide(medications: list[str]) -> bool:
    """Return True if the patient's medication list includes pyrazinamide."""
    for med in medications:
        lc = med.lower().strip()
        if "pyrazinamide" in lc or lc in ("pza", "z") or lc.startswith("pza "):
            return True
    return False


def _has_dengue_hypothesis(
    known_conditions: list[str],
    diagnosis_hypotheses: list[str],
) -> bool:
    """Return True if dengue appears in conditions or diagnosis hypotheses."""
    for item in known_conditions + diagnosis_hypotheses:
        if "dengue" in item.lower():
            return True
    return False


def _select_ranges(age: int, sex: str) -> dict[str, tuple[float, float]]:
    if age < 12:
        return PEDIATRIC_RANGES
    if sex.lower() == "female":
        return ADULT_FEMALE_RANGES
    return ADULT_MALE_RANGES


# ===========================================================================
# Step 2 — regex parsing
# ===========================================================================


def parse_rft(raw_text: str) -> dict[str, float]:
    """
    Extract RFT marker values from free-text lab reports.
    Strips Indian comma-formatting before float conversion.
    Silently skips any value that cannot be parsed.
    """
    parsed: dict[str, float] = {}
    for marker, pattern in RFT_MARKER_PATTERNS.items():
        match = pattern.search(raw_text)
        if not match:
            continue
        value_str = match.group(1).replace(",", "")
        try:
            parsed[marker] = float(value_str)
        except ValueError:
            logger.debug("parse_rft: could not convert %r to float for %s", value_str, marker)
    return parsed


# ===========================================================================
# Step 3 — abnormal flag detection
# ===========================================================================


def _get_rft_severity(
    marker: str,
    value: float,
    direction: str,
    deviation: float,
) -> str:
    """Return 'critical', 'moderate', or 'mild' for a given out-of-range value."""
    # Critical threshold check
    if marker in CRITICAL_RFT:
        thresholds = CRITICAL_RFT[marker]
        if direction == "low"  and "low"  in thresholds and value <= thresholds["low"]:
            return "critical"
        if direction == "high" and "high" in thresholds and value >= thresholds["high"]:
            return "critical"

    # Moderate hyperkalemia — elevate before reaching critical threshold
    if marker == "potassium" and direction == "high" and value >= _K_WARN:
        return "moderate"

    if deviation > 0.50:
        return "critical"
    if deviation > 0.20:
        return "moderate"
    return "mild"


def flag_rft_abnormals(
    parsed: dict[str, float],
    ranges: dict[str, tuple[float, float]],
    is_pyrazinamide: bool,
    has_dengue: bool,
) -> list[dict]:
    """
    Flag out-of-range RFT values.
    Annotates uric_acid / creatinine flags with ATT warning when on pyrazinamide.
    Annotates creatinine / urea flags with Dengue-AKI warning when dengue suspected.
    Adds escalation_required on any critical potassium flag.
    """
    flags: list[dict] = []

    for marker, value in parsed.items():
        if marker not in ranges:
            continue
        low, high = ranges[marker]

        # eGFR: flag only when LOW (high eGFR is never pathological)
        if marker == "egfr" and value >= low:
            continue

        flag: dict | None = None

        if value < low:
            deviation = (low - value) / low
            severity = _get_rft_severity(marker, value, "low", deviation)
            flag = {
                "marker":          marker,
                "value":           str(value),
                "reference_range": f"{low} – {high}",
                "direction":       "low",
                "severity":        severity,
                "interpretation":  f"{marker} is LOW at {value}",
            }
        elif value > high:
            deviation = (value - high) / high
            severity = _get_rft_severity(marker, value, "high", deviation)
            interp = f"{marker} is HIGH at {value}"
            if marker == "potassium" and value >= 6.5:
                interp = f"CRITICAL HYPERKALEMIA: K = {value} mEq/L — cardiac arrest risk"
            flag = {
                "marker":          marker,
                "value":           str(value),
                "reference_range": f"{low} – {high}",
                "direction":       "high",
                "severity":        severity,
                "interpretation":  interp,
            }

        if flag is None:
            continue

        # Context-sensitive annotations
        if is_pyrazinamide and marker in ("uric_acid", "creatinine"):
            flag["att_warning"] = _ATT_NEPHRO_WARNING
        if has_dengue and marker in ("creatinine", "urea", "bun"):
            flag["dengue_warning"] = _DENGUE_AKI_WARNING
        if marker == "potassium" and flag.get("severity") == "critical":
            flag["escalation_required"] = True
            flag["escalation_reason"]   = _CRITICAL_K_WARNING

        flags.append(flag)

    return flags


# ===========================================================================
# Step 4 — pattern detection
# ===========================================================================


def detect_rft_patterns(
    parsed: dict[str, float],
    flags: list[dict],
    known_conditions: list[str],
    current_medications: list[str],
    diagnosis_hypotheses: list[str],
) -> list[dict]:
    """
    Match parsed RFT values against the clinical pattern library.
    Handles plain high/low criteria, ratio checks (urea:creatinine),
    and context gates (dengue_context, att_medication).
    """
    flagged_low  = {f["marker"] for f in flags if f["direction"] == "low"}
    flagged_high = {f["marker"] for f in flags if f["direction"] == "high"}

    is_pza     = _is_on_pyrazinamide(current_medications)
    has_dengue = _has_dengue_hypothesis(known_conditions, diagnosis_hypotheses)

    matched: list[dict] = []

    for pattern in RFT_PATTERNS:
        # Context gates — skip if environmental condition is absent
        if pattern.get("dengue_context") and not has_dengue:
            continue
        if pattern.get("att_medication") and not is_pza:
            continue

        criteria_total = len(pattern["criteria"])
        criteria_met   = 0

        for marker, condition in pattern["criteria"].items():
            if condition == "high" and marker in flagged_high:
                criteria_met += 1
            elif condition == "low" and marker in flagged_low:
                criteria_met += 1

        # Derived ratio check (same mechanism as LFT interpreter)
        if "ratio_check" in pattern:
            for ratio_key, threshold in pattern["ratio_check"].items():
                num_m, denom_m = ratio_key.split("/")
                if num_m in parsed and denom_m in parsed and parsed[denom_m] > 0:
                    criteria_total += 1
                    if (parsed[num_m] / parsed[denom_m]) >= threshold:
                        criteria_met += 1

        if criteria_total == 0:
            continue
        match_ratio = criteria_met / criteria_total
        if match_ratio < 0.66:
            continue

        note = pattern["note"]
        # Append Dengue co-annotation to all non-Dengue patterns when dengue is suspected
        if has_dengue and "Dengue" not in pattern["name"]:
            note += " | ⚠️ Dengue in differential — monitor for Dengue-AKI progression."

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
    current_medications: list[str],
    diagnosis_hypotheses: list[str],
    parsed: dict,
    flags: list[dict],
    patterns: list[dict],
    ckd_stage_str: str,
) -> dict | None:
    prompt = _render_groq_prompt(
        age, sex, known_conditions, current_medications,
        diagnosis_hypotheses, parsed, flags, patterns, ckd_stage_str,
    )
    try:
        response = await _get_groq().chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user",   "content": "Interpret this RFT report now."},
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
        "clinical_summary":    f"RFT shows {len(flags)} abnormal finding(s). Pattern: {primary}.",
        "primary_finding":     primary,
        "risk_level":          risk,
        "risk_reason":         "Determined from abnormal flag severity",
        "immediate_actions":   [],
        "follow_up_tests":     [],
        "india_context":       "Groq synthesis unavailable — rule-based assessment only",
        "patient_explanation": "Some kidney function test values are outside normal range. "
                               "Please consult your doctor for a full explanation.",
        "monitoring_needed":   risk in ("high", "critical"),
    }


# ===========================================================================
# Main interpreter function
# ===========================================================================


async def interpret_rft(inputs: dict) -> dict:
    """
    Full RFT interpretation pipeline:
    parse → flag (with ATT/Dengue annotations) → pattern match →
    Groq nephrology synthesis → structured result.

    Expected inputs keys:
      raw_text, patient_age, patient_sex, known_conditions,
      current_medications (optional), diagnosis_hypotheses (optional)

    diagnosis_hypotheses may be list[str] or list[dict] (with 'diagnosis' key).
    """
    raw_text: str                  = inputs.get("raw_text", "")
    age: int                       = int(inputs.get("patient_age", 30))
    sex: str                       = str(inputs.get("patient_sex", "male"))
    known_conditions: list[str]    = inputs.get("known_conditions", [])
    current_medications: list[str] = inputs.get("current_medications", [])

    # Normalise diagnosis_hypotheses to plain strings
    raw_hypotheses = inputs.get("diagnosis_hypotheses", [])
    diagnosis_hypotheses: list[str] = [
        (h["diagnosis"] if isinstance(h, dict) else str(h))
        for h in raw_hypotheses
    ]

    is_pza     = _is_on_pyrazinamide(current_medications)
    has_dengue = _has_dengue_hypothesis(known_conditions, diagnosis_hypotheses)

    logger.info(
        "interpret_rft | age=%d | sex=%s | pza=%s | dengue=%s | text_len=%d",
        age, sex, is_pza, has_dengue, len(raw_text),
    )

    ranges = _select_ranges(age, sex)

    # Steps 2–4: pure Python, never raise
    parsed   = parse_rft(raw_text)
    flags    = flag_rft_abnormals(parsed, ranges, is_pza, has_dengue)
    patterns = detect_rft_patterns(
        parsed, flags, known_conditions, current_medications, diagnosis_hypotheses
    )

    logger.info(
        "interpret_rft | parsed=%d markers | flags=%d | patterns=%d",
        len(parsed), len(flags), len(patterns),
    )

    # CKD staging from eGFR when available
    ckd_stage_str = "eGFR not reported"
    if "egfr" in parsed:
        ckd_stage_str = ckd_stage(parsed["egfr"])

    # Step 5: Groq synthesis (optional — falls back to rule-based on failure)
    groq_result = await _groq_synthesize(
        age, sex, known_conditions, current_medications, diagnosis_hypotheses,
        parsed, flags, patterns, ckd_stage_str,
    )
    synthesis = groq_result if groq_result else _fallback_result(parsed, flags, patterns)

    primary_pattern = patterns[0]["pattern"] if patterns else None

    # Collect flags that require immediate escalation
    escalation_flags = [
        f for f in flags
        if f.get("severity") == "critical" or f.get("escalation_required")
    ]

    result = {
        "report_type":         "RFT",
        "parsed_values":       parsed,
        "values_count":        len(parsed),
        "abnormal_flags":      flags,
        "abnormal_count":      len(flags),
        "patterns_detected":   patterns,
        "primary_pattern":     primary_pattern,
        "ckd_stage":           ckd_stage_str,
        "escalation_flags":    escalation_flags,
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
        "interpret_rft OK | risk=%s | pattern=%s | ckd=%s | groq=%s",
        result["risk_level"],
        primary_pattern or "none",
        ckd_stage_str,
        "yes" if groq_result else "fallback",
    )
    return result
