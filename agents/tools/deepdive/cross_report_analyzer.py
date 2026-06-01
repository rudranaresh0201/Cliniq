"""
ClinIQ 2.0 — Cross-report pattern analyzer.

Reads ALL lab reports for a case and detects clinical patterns that no
single report can see.  This is a read-only aggregation layer that sits
on top of the individual CBC / LFT / RFT interpreters and never modifies
their output.

Public API:
  fetch_case_labs(case_id)  → list[LabReport], oldest-first
  cross_analyze(case_id)    → CrossAnalysisResult

Pattern detectors (all pure-Python, no I/O):
  1. Hepatorenal pattern        — concurrent liver + kidney dysfunction
  2. Dengue severity progression — platelet time-series across CBC reports
  3. Pancytopenia + hepatitis   — marrow suppression co-occurring with LFT rise
  4. ATT triple toxicity        — liver + kidney + anaemia on TB treatment
  5. Multi-parameter trajectory — per-marker trend across same-type reports
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from groq import AsyncGroq

from db.models import Escalation, LabReport
from db.supabase_client import (
    TABLE_LAB_REPORTS,
    create_escalation,
    get_case,
    get_client,
    get_patient,
)

logger = logging.getLogger("cliniq.tools.deepdive.cross_report")

_GROQ_MODEL = "llama-3.3-70b-versatile"

# ===========================================================================
# Data structures
# ===========================================================================


@dataclass
class DetectedPattern:
    name: str
    detected: bool
    confidence: float        # 0.0 – 1.0
    severity: str            # "watch" | "alert" | "emergency"
    reasoning: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class CrossAnalysisResult:
    case_id: str
    reports_analyzed: int
    patterns_detected: list[DetectedPattern]   # only patterns where detected=True
    trajectory: dict[str, str]                 # "{type}.{marker}" → "improving|stable|deteriorating"
    escalation_required: bool
    escalation_reason: str
    groq_synthesis: str
    analyzed_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


# ===========================================================================
# Marker directionality — determines which direction means "deteriorating"
# ===========================================================================

# Rising trend = deteriorating for these markers
_HIGHER_IS_WORSE = frozenset({
    "creatinine", "urea", "bun", "uric_acid",
    "sgot_ast", "sgpt_alt", "total_bilirubin", "direct_bilirubin",
    "alkaline_phosphatase", "ggt", "pt_inr",
    "potassium", "phosphorus",
})

# Falling trend = deteriorating for these markers
_LOWER_IS_WORSE = frozenset({
    "hemoglobin", "rbc", "hematocrit", "platelets", "wbc",
    "albumin", "egfr", "creatinine_clearance",
    "bicarbonate", "sodium",
})

# Clinical significance thresholds for trajectory (minimum relative change to flag)
_TRAJECTORY_THRESHOLD = 0.10   # 10% relative change = not "stable"


# ===========================================================================
# Low-level helpers
# ===========================================================================


def _parsed_values(report: LabReport) -> dict[str, float]:
    """
    Return a clean {marker: float} dict from a report's parsed_values.
    Falls back to deep_dive_output['parsed_values'] if the top-level dict
    is empty (handles reports saved before the analysis update step ran).
    """
    pv = report.parsed_values
    if not pv:
        pv = report.deep_dive_output.get("parsed_values", {})
    return {k: float(v) for k, v in pv.items() if isinstance(v, (int, float))}


def _has_any_abnormal(report: LabReport) -> bool:
    """True if the report has at least one flagged abnormal value."""
    if report.abnormal_flags:
        return True
    return bool(report.deep_dive_output.get("abnormal_count", 0))


def _trend(values: list[float], marker: str) -> str:
    """
    Simple first-vs-last linear trend.
    Returns 'improving' | 'stable' | 'deteriorating' | 'insufficient_data'.
    """
    if len(values) < 2:
        return "insufficient_data"
    first, last = values[0], values[-1]
    if first == 0:
        return "stable"
    relative_change = (last - first) / abs(first)
    if abs(relative_change) < _TRAJECTORY_THRESHOLD:
        return "stable"
    rising = last > first
    if marker in _HIGHER_IS_WORSE:
        return "deteriorating" if rising else "improving"
    if marker in _LOWER_IS_WORSE:
        return "deteriorating" if not rising else "improving"
    # Directionality unknown — report raw direction
    return "rising" if rising else "falling"


def _group_by_type(
    reports: list[LabReport],
) -> dict[str, list[LabReport]]:
    """Partition reports into {report_type: [oldest … newest]}."""
    grouped: dict[str, list[LabReport]] = {}
    for r in reports:
        grouped.setdefault(r.report_type, []).append(r)
    return grouped


def _is_on_att(known_conditions: list[str], current_medications: list[str]) -> bool:
    """Return True if the patient appears to be on anti-tuberculosis therapy."""
    haystack = " ".join(known_conditions + current_medications).lower()
    att_signals = (
        "tuberculosis", "rifampicin", "rifampin", "isoniazid",
        "pyrazinamide", "ethambutol", "streptomycin",
    )
    if any(s in haystack for s in att_signals):
        return True
    # Catch common abbreviations like " TB " (with word boundaries)
    return " tb " in f" {haystack} " or haystack.startswith("tb ")


# ===========================================================================
# Pattern detector 1 — Hepatorenal
# ===========================================================================

# Thresholds mirroring the LFT / RFT interpreters
_BILI_THRESHOLD    = 2.0    # mg/dL  (spec: bilirubin >2)
_SGOT_3X_ULN      = 120.0  # IU/L   (3 × ULN 40)
_SGPT_3X_ULN      = 168.0  # IU/L   (3 × ULN 56)
_CREAT_ELEVATED   = 1.5    # mg/dL
_CREAT_RISE_PCT   = 25.0   # % rise across RFT reports = "rising"


def _detect_hepatorenal(
    reports_by_type: dict[str, list[LabReport]],
) -> DetectedPattern:
    lft_list = reports_by_type.get("LFT", [])
    rft_list = reports_by_type.get("RFT", [])

    if not lft_list or not rft_list:
        return DetectedPattern(
            name="Hepatorenal Pattern",
            detected=False, confidence=0.0, severity="watch",
            reasoning="Requires ≥1 LFT and ≥1 RFT report.",
        )

    # --- LFT side ---
    lft_abnormal = False
    lft_evidence: list[str] = []
    for r in lft_list:
        pv = _parsed_values(r)
        bili  = pv.get("total_bilirubin", 0.0)
        sgot  = pv.get("sgot_ast", 0.0)
        sgpt  = pv.get("sgpt_alt", 0.0)
        if bili > _BILI_THRESHOLD:
            lft_abnormal = True
            lft_evidence.append(f"Bilirubin {bili:.1f} mg/dL (>{_BILI_THRESHOLD})")
        if sgot > _SGOT_3X_ULN:
            lft_abnormal = True
            lft_evidence.append(f"SGOT {sgot:.0f} IU/L (>3× ULN)")
        if sgpt > _SGPT_3X_ULN:
            lft_abnormal = True
            lft_evidence.append(f"SGPT {sgpt:.0f} IU/L (>3× ULN)")

    # --- RFT side: creatinine elevated or rising ---
    rft_abnormal = False
    rft_evidence: list[str] = []
    creat_values = [
        pv["creatinine"]
        for r in rft_list
        if (pv := _parsed_values(r)) and "creatinine" in pv
    ]
    if creat_values:
        latest = creat_values[-1]
        if latest > _CREAT_ELEVATED:
            rft_abnormal = True
            rft_evidence.append(f"Creatinine {latest:.2f} mg/dL (>{_CREAT_ELEVATED})")
        if len(creat_values) >= 2:
            rise = (creat_values[-1] - creat_values[0]) / max(creat_values[0], 0.01) * 100
            if rise > _CREAT_RISE_PCT:
                rft_abnormal = True
                rft_evidence.append(
                    f"Creatinine rising: {creat_values[0]:.2f}→{creat_values[-1]:.2f} "
                    f"(+{rise:.0f}%)"
                )

    detected = lft_abnormal and rft_abnormal
    return DetectedPattern(
        name="Hepatorenal Pattern",
        detected=detected,
        confidence=0.85 if detected else 0.0,
        severity="emergency" if detected else "watch",
        reasoning=(
            "Concurrent liver dysfunction and renal impairment detected. "
            "Differential: hepatorenal syndrome (type 1/2), leptospirosis, "
            "severe dengue with multi-organ involvement, sepsis. "
            "Nephrology + hepatology urgent review; IV albumin + vasopressors if HRS confirmed."
            if detected else
            "LFT and RFT criteria not simultaneously met."
        ),
        evidence=lft_evidence + rft_evidence,
    )


# ===========================================================================
# Pattern detector 2 — Dengue severity progression
# ===========================================================================

_PLT_ALERT_K     = 50.0    # platelets <50k → alert
_PLT_EMERGENCY_K = 20.0    # platelets <20k → emergency (DHF risk)
_PLT_FIRST_MIN   = 100.0   # first reading should have been >100k for progression


def _detect_dengue_progression(
    reports_by_type: dict[str, list[LabReport]],
) -> DetectedPattern:
    cbc_list = reports_by_type.get("CBC", [])

    if len(cbc_list) < 2:
        return DetectedPattern(
            name="Dengue Severity Progression",
            detected=False, confidence=0.0, severity="watch",
            reasoning="Requires ≥2 CBC reports for platelet time-series analysis.",
        )

    # Build platelet time-series (values in ×10³/µL)
    plt_series: list[float] = [
        pv["platelets"]
        for r in cbc_list
        if (pv := _parsed_values(r)) and "platelets" in pv
    ]

    if len(plt_series) < 2:
        return DetectedPattern(
            name="Dengue Severity Progression",
            detected=False, confidence=0.0, severity="watch",
            reasoning="Platelet data absent in multiple CBC reports.",
        )

    first_plt, latest_plt = plt_series[0], plt_series[-1]
    declining = latest_plt < first_plt
    drop_pct  = (first_plt - latest_plt) / max(first_plt, 0.01) * 100
    evidence  = [f"Platelet trend: {first_plt:.0f}k → {latest_plt:.0f}k/µL (−{drop_pct:.0f}%)"]

    # Emergency: latest <20k — Dengue Haemorrhagic Fever risk
    if latest_plt < _PLT_EMERGENCY_K and declining:
        return DetectedPattern(
            name="Dengue Severity Progression",
            detected=True, confidence=0.90, severity="emergency",
            reasoning=(
                f"Platelets critically low at {latest_plt:.0f}k/µL and falling from "
                f"{first_plt:.0f}k/µL — Dengue Haemorrhagic Fever risk. "
                "Immediate hospitalisation, IV access, monitor for spontaneous bleeding "
                "(gingival, petechiae, epistaxis). Platelet transfusion threshold: <10k."
            ),
            evidence=evidence,
        )

    # Alert: latest <50k with significant drop from >100k baseline
    if latest_plt < _PLT_ALERT_K and first_plt > _PLT_FIRST_MIN and declining:
        return DetectedPattern(
            name="Dengue Severity Progression",
            detected=True, confidence=0.80, severity="alert",
            reasoning=(
                f"Platelets falling: {first_plt:.0f}k → {latest_plt:.0f}k/µL — "
                "classic dengue nadir pattern. Monitor q12h for further drop. "
                "Strict bed rest; avoid NSAIDs, aspirin, intramuscular injections. "
                "Watch for warning signs: abdominal pain, vomiting, mucosal bleed."
            ),
            evidence=evidence,
        )

    # Watch: any significant declining trend from normal baseline
    if declining and first_plt > _PLT_FIRST_MIN and drop_pct > 30:
        return DetectedPattern(
            name="Dengue Severity Progression",
            detected=True, confidence=0.65, severity="watch",
            reasoning=(
                f"Platelet count declining ({drop_pct:.0f}% fall) — monitor for dengue-pattern "
                f"thrombocytopenia. Next CBC in 24–48 h."
            ),
            evidence=evidence,
        )

    return DetectedPattern(
        name="Dengue Severity Progression",
        detected=False, confidence=0.0, severity="watch",
        reasoning="Platelet trend stable or not meeting dengue progression thresholds.",
    )


# ===========================================================================
# Pattern detector 3 — Pancytopenia + hepatitis
# ===========================================================================

_HGB_PANCYTOPENIA  = 10.0   # g/dL
_WBC_PANCYTOPENIA  = 4.0    # ×10³/µL
_PLT_PANCYTOPENIA  = 100.0  # ×10³/µL
_SGOT_2X_ULN       = 80.0   # IU/L  (2 × ULN 40)
_SGPT_2X_ULN       = 112.0  # IU/L  (2 × ULN 56)


def _detect_pancytopenia_hepatitis(
    reports_by_type: dict[str, list[LabReport]],
) -> DetectedPattern:
    cbc_list = reports_by_type.get("CBC", [])
    lft_list = reports_by_type.get("LFT", [])

    if not cbc_list or not lft_list:
        return DetectedPattern(
            name="Pancytopenia with Hepatitis",
            detected=False, confidence=0.0, severity="watch",
            reasoning="Requires ≥1 CBC and ≥1 LFT report.",
        )

    # Latest CBC — all three cell lines depressed
    cbc_pv = _parsed_values(cbc_list[-1])
    hgb = cbc_pv.get("hemoglobin", 999.0)
    wbc = cbc_pv.get("wbc",        999.0)
    plt = cbc_pv.get("platelets",  999.0)

    pancytopenia = hgb < _HGB_PANCYTOPENIA and wbc < _WBC_PANCYTOPENIA and plt < _PLT_PANCYTOPENIA
    cbc_evidence: list[str] = []
    if pancytopenia:
        cbc_evidence.append(
            f"Pancytopenia: Hgb {hgb:.1f} g/dL / WBC {wbc:.1f}k / Plt {plt:.0f}k"
        )

    # Latest LFT — transaminitis ≥ 2× ULN
    lft_pv    = _parsed_values(lft_list[-1])
    sgot      = lft_pv.get("sgot_ast",  0.0)
    sgpt      = lft_pv.get("sgpt_alt",  0.0)
    transaminitis = sgot > _SGOT_2X_ULN or sgpt > _SGPT_2X_ULN
    lft_evidence: list[str] = []
    if transaminitis:
        if sgot > _SGOT_2X_ULN:
            lft_evidence.append(f"SGOT {sgot:.0f} IU/L (>2× ULN)")
        if sgpt > _SGPT_2X_ULN:
            lft_evidence.append(f"SGPT {sgpt:.0f} IU/L (>2× ULN)")

    detected = pancytopenia and transaminitis
    return DetectedPattern(
        name="Pancytopenia with Hepatitis",
        detected=detected,
        confidence=0.85 if detected else 0.0,
        severity="alert" if detected else "watch",
        reasoning=(
            "All three cell lines suppressed with concurrent hepatitis. "
            "Differential (India context): viral hepatitis with marrow suppression "
            "(EBV, CMV, Hepatitis B/C), visceral leishmaniasis (kala-azar — check splenomegaly), "
            "enteric fever (typhoid), disseminated TB, drug-induced (ATT, anti-fungals, "
            "chemotherapy). Haematology + gastroenterology review; bone marrow trephine "
            "if no infective cause found."
            if detected else
            "Pancytopenia and hepatitis not simultaneously present."
        ),
        evidence=cbc_evidence + lft_evidence,
    )


# ===========================================================================
# Pattern detector 4 — ATT triple toxicity
# ===========================================================================

_HGB_ANEMIA       = 10.0  # g/dL — moderate anaemia threshold
_CREAT_ATT_THRESH = 1.5   # mg/dL
_URIC_ATT_THRESH  = 8.0   # mg/dL (pyrazinamide-driven hyperuricaemia)


def _detect_att_triple_toxicity(
    reports_by_type: dict[str, list[LabReport]],
    known_conditions: list[str],
    current_medications: list[str],
) -> DetectedPattern:
    if not _is_on_att(known_conditions, current_medications):
        return DetectedPattern(
            name="ATT Triple Toxicity",
            detected=False, confidence=0.0, severity="watch",
            reasoning="Patient not identified as being on anti-tuberculosis therapy.",
        )

    cbc_list = reports_by_type.get("CBC", [])
    lft_list = reports_by_type.get("LFT", [])
    rft_list = reports_by_type.get("RFT", [])

    evidence = ["Patient on anti-tuberculosis therapy (ATT)"]
    organs_affected = 0

    # Bone marrow / haematopoiesis — anaemia
    if cbc_list:
        pv  = _parsed_values(cbc_list[-1])
        hgb = pv.get("hemoglobin", 999.0)
        if hgb < _HGB_ANEMIA:
            organs_affected += 1
            evidence.append(f"ATT anaemia: Hgb {hgb:.1f} g/dL")

    # Hepatotoxicity — SGOT/SGPT/bilirubin elevated
    if lft_list:
        pv   = _parsed_values(lft_list[-1])
        sgot = pv.get("sgot_ast",       0.0)
        sgpt = pv.get("sgpt_alt",       0.0)
        bili = pv.get("total_bilirubin", 0.0)
        if sgot > _SGOT_2X_ULN or sgpt > _SGPT_2X_ULN or bili > _BILI_THRESHOLD:
            organs_affected += 1
            evidence.append(
                f"ATT hepatotoxicity: ALT {sgpt:.0f} / AST {sgot:.0f} / Bil {bili:.1f}"
            )

    # Nephrotoxicity / hyperuricaemia — creatinine rise or high uric acid
    if rft_list:
        pv        = _parsed_values(rft_list[-1])
        creat     = pv.get("creatinine", 0.0)
        uric_acid = pv.get("uric_acid",  0.0)
        if creat > _CREAT_ATT_THRESH or uric_acid > _URIC_ATT_THRESH:
            organs_affected += 1
            evidence.append(
                f"ATT nephrotoxicity/hyperuricaemia: Creat {creat:.2f} / UA {uric_acid:.1f}"
            )

    # Full triple toxicity: all three organ systems affected
    if organs_affected >= 3:
        return DetectedPattern(
            name="ATT Triple Toxicity",
            detected=True, confidence=0.90, severity="emergency",
            reasoning=(
                "Multi-organ drug toxicity in ATT patient: anaemia + hepatotoxicity + "
                "nephrotoxicity concurrently. "
                "STOP ALL ATT IMMEDIATELY. Urgent TB physician and hepatology review. "
                "Identify the offending drug (pyrazinamide → uric acid/renal; "
                "isoniazid/rifampicin → liver). Re-check LFT + RFT + CBC at 48 h. "
                "Restart modified ATT regimen after organ recovery."
            ),
            evidence=evidence,
        )

    # Two-organ warning
    if organs_affected == 2:
        return DetectedPattern(
            name="ATT Triple Toxicity",
            detected=True, confidence=0.75, severity="alert",
            reasoning=(
                f"ATT patient with {organs_affected} organ systems showing drug-related "
                "abnormalities. Consider temporary dose reduction or drug holiday. "
                "Urgent TB physician review; closely monitor remaining organ system."
            ),
            evidence=evidence,
        )

    return DetectedPattern(
        name="ATT Triple Toxicity",
        detected=False, confidence=0.0, severity="watch",
        reasoning=(
            f"ATT patient — {organs_affected} organ system(s) affected. "
            "Routine monitoring; ensure LFT + RFT + CBC at each ATT review visit."
        ),
        evidence=evidence[:1],
    )


# ===========================================================================
# Trajectory computation
# ===========================================================================


def _compute_trajectories(
    reports_by_type: dict[str, list[LabReport]],
) -> dict[str, str]:
    """
    For each marker present in ≥2 reports of the same type, compute
    the first-vs-last trend.  Key format: "{ReportType}.{marker}".
    """
    trajectory: dict[str, str] = {}
    for rtype, reports in reports_by_type.items():
        if len(reports) < 2:
            continue
        all_markers: set[str] = set()
        for r in reports:
            all_markers.update(_parsed_values(r).keys())
        for marker in all_markers:
            values = [
                _parsed_values(r)[marker]
                for r in reports
                if marker in _parsed_values(r)
            ]
            if len(values) < 2:
                continue
            t = _trend(values, marker)
            if t != "insufficient_data":
                trajectory[f"{rtype}.{marker}"] = t
    return trajectory


# ===========================================================================
# Groq narrative synthesis
# ===========================================================================

_GROQ_PROMPT = """You are a senior physician reviewing automated cross-report lab analysis for a patient in India.

Case:
- Chief complaint: PLACEHOLDER_COMPLAINT
- Risk tier: PLACEHOLDER_RISK_TIER
- Known conditions: PLACEHOLDER_CONDITIONS
- Medications: PLACEHOLDER_MEDICATIONS

Reports analyzed: PLACEHOLDER_N_REPORTS (PLACEHOLDER_TYPES)

Cross-report patterns detected:
PLACEHOLDER_PATTERNS

Parameter trajectories across serial reports:
PLACEHOLDER_TRAJECTORIES

Write a concise clinical narrative summary (3-5 sentences) for the attending doctor.
Focus on: (1) what the combined findings mean together, (2) the single most urgent action, \
(3) any India-specific context relevant to the pattern (dengue, TB, leptospirosis, kala-azar, etc.).
Write in plain clinical English — no bullet points, no headers, no JSON.
Return ONLY the narrative text."""


async def _groq_narrative(
    patterns: list[DetectedPattern],
    trajectory: dict[str, str],
    chief_complaint: str,
    risk_tier: str,
    known_conditions: list[str],
    current_medications: list[str],
    n_reports: int,
    report_types: list[str],
) -> str:
    """Generate a doctor-facing narrative. Returns a rule-based fallback if Groq fails."""
    pattern_text = json.dumps(
        [
            {"name": p.name, "severity": p.severity, "reasoning": p.reasoning,
             "evidence": p.evidence}
            for p in patterns
        ],
        indent=2,
    )
    traj_text = json.dumps(trajectory, indent=2) if trajectory else "No serial reports available."

    prompt = (
        _GROQ_PROMPT
        .replace("PLACEHOLDER_COMPLAINT",   chief_complaint or "not specified")
        .replace("PLACEHOLDER_RISK_TIER",   risk_tier)
        .replace("PLACEHOLDER_CONDITIONS",  ", ".join(known_conditions) or "none")
        .replace("PLACEHOLDER_MEDICATIONS", ", ".join(current_medications) or "none")
        .replace("PLACEHOLDER_N_REPORTS",   str(n_reports))
        .replace("PLACEHOLDER_TYPES",       ", ".join(sorted(set(report_types))))
        .replace("PLACEHOLDER_PATTERNS",    pattern_text)
        .replace("PLACEHOLDER_TRAJECTORIES", traj_text)
    )

    try:
        client = _get_groq()
        response = await client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user",   "content": "Write the clinical narrative now."},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("_groq_narrative: Groq call failed — using rule-based fallback")

    # Rule-based fallback
    if not patterns:
        return (
            f"Cross-report analysis of {n_reports} lab report(s) "
            f"({', '.join(sorted(set(report_types)))}) did not reveal any inter-report "
            "escalation patterns. Continue monitoring as scheduled."
        )
    highest = max(patterns, key=lambda p: {"emergency": 2, "alert": 1, "watch": 0}.get(p.severity, 0))
    deteriorating = [k for k, v in trajectory.items() if v == "deteriorating"]
    traj_note = (
        f" Deteriorating parameters: {', '.join(deteriorating)}." if deteriorating else ""
    )
    return (
        f"Cross-report analysis detected {len(patterns)} pattern(s): "
        f"{'; '.join(p.name for p in patterns)}. "
        f"Most urgent: {highest.name} — {highest.reasoning}"
        f"{traj_note} Immediate clinical review recommended."
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
# DB helpers
# ===========================================================================


async def fetch_case_labs(case_id: UUID) -> list[LabReport]:
    """
    Fetch all lab_reports for a case ordered by uploaded_at ascending
    (oldest first) for time-series analysis.
    """
    try:
        db  = await get_client()
        res = (
            await db.table(TABLE_LAB_REPORTS)
            .select("*")
            .eq("case_id", str(case_id))
            .order("uploaded_at", desc=False)
            .execute()
        )
        return [LabReport(**row) for row in res.data]
    except Exception:
        logger.exception("fetch_case_labs failed for case_id=%s", case_id)
        raise


async def _persist_escalation(
    case_id: UUID,
    patient_id: UUID,
    worst_pattern: DetectedPattern,
    all_patterns: list[DetectedPattern],
    trajectory: dict[str, str],
) -> str | None:
    """Create an Escalation row in Supabase and flip the case status."""
    try:
        severity_map = {"emergency": "emergency", "alert": "alert", "watch": "watch"}
        escalation = Escalation(
            case_id=case_id,
            patient_id=patient_id,
            severity=severity_map.get(worst_pattern.severity, "alert"),  # type: ignore[arg-type]
            trigger_reason=worst_pattern.reasoning,
            trigger_evidence={
                "source":         "cross_report_analyzer",
                "patterns":       [
                    {"name": p.name, "severity": p.severity, "evidence": p.evidence}
                    for p in all_patterns
                ],
                "trajectory":     trajectory,
                "worst_pattern":  worst_pattern.name,
            },
            checkpoint_context={},
        )
        saved = await create_escalation(escalation)
        eid = str(saved.escalation_id) if saved.escalation_id else None
        logger.info(
            "_persist_escalation | id=%s | severity=%s | pattern=%s",
            eid, worst_pattern.severity, worst_pattern.name,
        )
        return eid
    except Exception:
        logger.exception("_persist_escalation failed for case_id=%s", case_id)
        return None


# ===========================================================================
# Main entry point
# ===========================================================================


async def cross_analyze(case_id: UUID) -> CrossAnalysisResult:
    """
    Run cross-report pattern analysis for a case.

    If ≥2 lab reports exist, detects multi-report patterns, computes
    parameter trajectories, synthesises a clinical narrative via Groq,
    and persists an Escalation row when escalation is warranted.

    Always returns a CrossAnalysisResult — never raises.
    """
    try:
        # 1. Fetch reports oldest-first
        reports = await fetch_case_labs(case_id)
    except Exception as exc:
        logger.exception("cross_analyze: fetch_case_labs failed for case_id=%s", case_id)
        return CrossAnalysisResult(
            case_id=str(case_id), reports_analyzed=0,
            patterns_detected=[], trajectory={},
            escalation_required=False, escalation_reason="",
            groq_synthesis=f"Cross-analysis unavailable: {exc}",
        )

    if len(reports) < 2:
        logger.info("cross_analyze | case=%s | only %d report(s) — skipping", case_id, len(reports))
        return CrossAnalysisResult(
            case_id=str(case_id), reports_analyzed=len(reports),
            patterns_detected=[], trajectory={},
            escalation_required=False, escalation_reason="",
            groq_synthesis="Fewer than 2 lab reports available; cross-analysis requires ≥2.",
        )

    logger.info("cross_analyze | case=%s | %d reports", case_id, len(reports))

    # 2. Load case context (best-effort — fall back to empty lists)
    known_conditions: list[str] = []
    current_medications: list[str] = []
    chief_complaint = "not specified"
    risk_tier       = "low"
    patient_id: UUID | None = None

    try:
        case = await get_case(case_id)
        if case:
            chief_complaint = case.chief_complaint or "not specified"
            risk_tier       = case.risk_tier or "low"
            patient_id      = case.patient_id  # type: ignore[assignment]
            patient = await get_patient(case.patient_id)  # type: ignore[arg-type]
            if patient:
                known_conditions    = patient.known_conditions or []
                current_medications = patient.current_medications or []
    except Exception:
        logger.exception("cross_analyze: could not load case/patient context for %s", case_id)

    # 3. Group reports by type (oldest first within each type)
    reports_by_type = _group_by_type(reports)
    report_types    = [r.report_type for r in reports]

    # 4. Run all pattern detectors (pure Python — no I/O, no exceptions)
    all_patterns = [
        _detect_hepatorenal(reports_by_type),
        _detect_dengue_progression(reports_by_type),
        _detect_pancytopenia_hepatitis(reports_by_type),
        _detect_att_triple_toxicity(
            reports_by_type, known_conditions, current_medications
        ),
    ]

    detected_patterns = [p for p in all_patterns if p.detected]

    # 5. Compute parameter trajectories
    trajectory = _compute_trajectories(reports_by_type)

    # 6. Determine escalation requirement (emergency or alert)
    _ESCALATION_SEVERITIES = frozenset({"emergency", "alert"})
    escalating = [p for p in detected_patterns if p.severity in _ESCALATION_SEVERITIES]
    escalation_required = bool(escalating)
    escalation_reason   = "; ".join(p.name for p in escalating)

    # 7. Persist escalation to Supabase when warranted
    if escalation_required and patient_id:
        worst = max(
            escalating,
            key=lambda p: 2 if p.severity == "emergency" else 1,
        )
        await _persist_escalation(
            case_id, patient_id, worst, detected_patterns, trajectory
        )

    # 8. Groq narrative synthesis
    groq_text = await _groq_narrative(
        patterns=detected_patterns,
        trajectory=trajectory,
        chief_complaint=chief_complaint,
        risk_tier=risk_tier,
        known_conditions=known_conditions,
        current_medications=current_medications,
        n_reports=len(reports),
        report_types=report_types,
    )

    result = CrossAnalysisResult(
        case_id=str(case_id),
        reports_analyzed=len(reports),
        patterns_detected=detected_patterns,
        trajectory=trajectory,
        escalation_required=escalation_required,
        escalation_reason=escalation_reason,
        groq_synthesis=groq_text,
    )

    logger.info(
        "cross_analyze OK | case=%s | reports=%d | patterns=%d | escalation=%s",
        case_id, len(reports), len(detected_patterns), escalation_required,
    )
    return result
