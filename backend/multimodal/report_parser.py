import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import re
import logging

logger = logging.getLogger("cliniq")

# ---------------------------------------------------------------------------
# Type-specific normal ranges
# ---------------------------------------------------------------------------

CBC_RANGES: dict[str, dict] = {
    "hemoglobin":   {"low": 12.0,   "high": 17.5,   "unit": "g/dL",       "critical_low": 7.0,   "critical_high": 20.0},
    "wbc":          {"low": 4000,   "high": 11000,  "unit": "/uL",         "critical_low": 2000,  "critical_high": 30000},
    "platelets":    {"low": 150000, "high": 400000, "unit": "/uL",         "critical_low": 50000, "critical_high": 1000000},
    "rbc":          {"low": 3.8,    "high": 5.5,    "unit": "million/uL",  "critical_low": 2.0,   "critical_high": 7.0},
    "hematocrit":   {"low": 36,     "high": 52,     "unit": "%",           "critical_low": 20,    "critical_high": 65},
    "neutrophils":  {"low": 40,     "high": 70,     "unit": "%",           "critical_low": 20,    "critical_high": 90},
    "lymphocytes":  {"low": 20,     "high": 40,     "unit": "%",           "critical_low": 5,     "critical_high": 60},
}

LFT_RANGES: dict[str, dict] = {
    "sgot":           {"low": 0,   "high": 40,  "unit": "U/L",   "critical_low": 0, "critical_high": 500},
    "sgpt":           {"low": 0,   "high": 40,  "unit": "U/L",   "critical_low": 0, "critical_high": 500},
    "alt":            {"low": 0,   "high": 40,  "unit": "U/L",   "critical_low": 0, "critical_high": 500},
    "ast":            {"low": 0,   "high": 40,  "unit": "U/L",   "critical_low": 0, "critical_high": 500},
    "bilirubin_total":{"low": 0.2, "high": 1.2, "unit": "mg/dL", "critical_low": 0, "critical_high": 15},
    "albumin":        {"low": 3.5, "high": 5.0, "unit": "g/dL",  "critical_low": 2.0, "critical_high": 6.0},
}

KFT_RANGES: dict[str, dict] = {
    "creatinine": {"low": 0.6, "high": 1.2, "unit": "mg/dL", "critical_low": 0,   "critical_high": 10},
    "bun":        {"low": 7,   "high": 20,  "unit": "mg/dL", "critical_low": 0,   "critical_high": 100},
    "uric_acid":  {"low": 2.4, "high": 7.0, "unit": "mg/dL", "critical_low": 0,   "critical_high": 12},
}

LIPID_RANGES: dict[str, dict] = {
    "total_cholesterol": {"low": 0,  "high": 200, "unit": "mg/dL", "critical_low": 0,  "critical_high": 300},
    "ldl":               {"low": 0,  "high": 100, "unit": "mg/dL", "critical_low": 0,  "critical_high": 190},
    "hdl":               {"low": 40, "high": 999, "unit": "mg/dL", "critical_low": 20, "critical_high": 999},
    "triglycerides":     {"low": 0,  "high": 150, "unit": "mg/dL", "critical_low": 0,  "critical_high": 500},
}

DIABETES_RANGES: dict[str, dict] = {
    "fasting_glucose": {"low": 70, "high": 100, "unit": "mg/dL", "critical_low": 40, "critical_high": 400},
    "hba1c":           {"low": 0,  "high": 5.7, "unit": "%",     "critical_low": 0,  "critical_high": 14},
    "ppbs":            {"low": 0,  "high": 140, "unit": "mg/dL", "critical_low": 0,  "critical_high": 500},
}

THYROID_RANGES: dict[str, dict] = {
    "tsh": {"low": 0.4, "high": 4.0,  "unit": "mIU/L", "critical_low": 0.01, "critical_high": 10},
    "t3":  {"low": 80,  "high": 200,  "unit": "ng/dL",  "critical_low": 40,   "critical_high": 400},
    "t4":  {"low": 5.0, "high": 12.0, "unit": "ug/dL",  "critical_low": 2.0,  "critical_high": 20},
}

REPORT_TYPE_RANGES: dict[str, dict] = {
    "cbc":      CBC_RANGES,
    "lft":      LFT_RANGES,
    "kft":      KFT_RANGES,
    "lipid":    LIPID_RANGES,
    "diabetes": DIABETES_RANGES,
    "thyroid":  THYROID_RANGES,
}

# ---------------------------------------------------------------------------
# Aliases: canonical key → list of text patterns to search for
# ---------------------------------------------------------------------------

TYPE_ALIASES: dict[str, dict[str, list[str]]] = {
    "cbc": {
        "hemoglobin":  ["hemoglobin", "haemoglobin", "hb", "hgb"],
        "wbc":         ["total wbc", "wbc", "total leucocyte count", "tlc", "total leukocyte count", "leucocyte"],
        "platelets":   ["platelet count", "platelet", "platelets", "plt", "thrombocyte"],
        "rbc":         ["rbc", "red blood cell", "erythrocyte"],
        "hematocrit":  ["hematocrit", "haematocrit", "pcv", "packed cell volume"],
        "neutrophils": ["neutrophil", "neutrophils", "pmn"],
        "lymphocytes": ["lymphocyte", "lymphocytes"],
    },
    "lft": {
        "sgot":            ["sgot", "ast", "aspartate aminotransferase"],
        "sgpt":            ["sgpt", "alt", "alanine aminotransferase"],
        "alt":             ["alt", "alanine"],
        "ast":             ["ast", "aspartate"],
        "bilirubin_total": ["total bilirubin", "bilirubin total", "bilirubin", "s.bilirubin"],
        "albumin":         ["albumin", "s.albumin", "serum albumin"],
    },
    "kft": {
        "creatinine": ["serum creatinine", "s.creatinine", "creatinine"],
        "bun":        ["blood urea nitrogen", "blood urea", "bun", "urea"],
        "uric_acid":  ["serum uric acid", "s.uric acid", "uric acid"],
    },
    "lipid": {
        "total_cholesterol": ["total cholesterol", "s.cholesterol", "cholesterol"],
        "ldl":               ["ldl cholesterol", "ldl-c", "ldl"],
        "hdl":               ["hdl cholesterol", "hdl-c", "hdl"],
        "triglycerides":     ["triglycerides", "triglyceride", "trig"],
    },
    "diabetes": {
        "fasting_glucose": ["fasting blood sugar", "blood sugar fasting", "fasting glucose", "fbs", "glucose fasting"],
        "hba1c":           ["glycated hemoglobin", "glycohaemoglobin", "hba1c", "a1c"],
        "ppbs":            ["post prandial blood sugar", "pp blood sugar", "ppbs", "2 hour glucose"],
    },
    "thyroid": {
        "tsh": ["thyroid stimulating hormone", "tsh"],
        "t3":  ["triiodothyronine", "t3"],
        "t4":  ["thyroxine", "t4"],
    },
}

# ---------------------------------------------------------------------------
# Report type detection
# ---------------------------------------------------------------------------

REPORT_KEYWORDS: dict[str, list[str]] = {
    "cbc":          ["hemoglobin", "wbc", "platelet", "rbc", "hematocrit", "tlc", "hgb", "haemoglobin"],
    "lft":          ["sgot", "sgpt", "bilirubin", "albumin", "alt", "ast", "liver function"],
    "kft":          ["creatinine", "bun", "egfr", "urea", "uric acid", "kidney function"],
    "thyroid":      ["tsh", "t3", "t4", "thyroid"],
    "lipid":        ["cholesterol", "ldl", "hdl", "triglyceride"],
    "diabetes":     ["hba1c", "fasting glucose", "blood sugar", "ppbs", "fbs"],
    "xray_report":  ["x-ray", "xray", "chest pa view", "opacity", "consolidation", "infiltrate", "pleural"],
    "mri_report":   ["mri", "t1", "t2", "flair", "hyperintensity", "hypointensity", "lesion", "atrophy"],
    "ct_report":    ["ct scan", "computed tomography", "hounsfield", "hypodense", "hyperdense"],
    "ecg_report":   ["ecg", "ekg", "sinus rhythm", "st segment", "qrs", "tachycardia", "bradycardia"],
    "urine":        ["urine", "pus cells", "epithelial", "albumin trace", "ketones", "urinalysis"],
    "prescription": ["prescription", "rx", "tab.", "cap.", "syrup", "twice daily", " od ", " bd ", " tds "],
}


def detect_report_type(text: str) -> str:
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for rtype, keywords in REPORT_KEYWORDS.items():
        scores[rtype] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general_medical"


# ---------------------------------------------------------------------------
# Flagging helper
# ---------------------------------------------------------------------------

def _flag(value: float, ref: dict) -> str:
    crit_high = ref.get("critical_high")
    crit_low  = ref.get("critical_low")
    if crit_high is not None and value > crit_high:
        return "CRITICAL_HIGH"
    if crit_low is not None and value < crit_low:
        return "CRITICAL_LOW"
    if value > ref["high"]:
        return "HIGH"
    if value < ref["low"]:
        return "LOW"
    return "NORMAL"


# ---------------------------------------------------------------------------
# Lab value extraction
# ---------------------------------------------------------------------------

def _extract_lab_values(text: str, report_type: str) -> dict[str, dict]:
    ranges = REPORT_TYPE_RANGES.get(report_type, {})
    if not ranges:
        return {}

    aliases = TYPE_ALIASES.get(report_type, {})
    text_lower = text.lower()
    found: dict[str, dict] = {}

    for canonical_key, ref in ranges.items():
        patterns = aliases.get(canonical_key, [canonical_key.replace("_", " ")])
        value: float | None = None

        for pattern in patterns:
            regex = re.compile(
                rf"{re.escape(pattern)}\s*[:\-]?\s*(\d{{1,6}}(?:\.\d{{1,3}})?)",
                re.IGNORECASE,
            )
            match = regex.search(text_lower)
            if match:
                value = float(match.group(1))
                break

        if value is not None:
            found[canonical_key] = {
                "value": value,
                "unit": ref["unit"],
                "normal_low": ref["low"],
                "normal_high": ref["high"],
                "flag": _flag(value, ref),
            }

    return found


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_text(file_bytes: bytes, content_type: str) -> str:
    if "pdf" in content_type:
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
            return ""
    # text/plain or any other type — decode as UTF-8
    return file_bytes.decode("utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_report(file_bytes: bytes, content_type: str) -> dict:
    # Step 1: Extract text
    raw_text = _extract_text(file_bytes, content_type)

    if not raw_text.strip():
        return {
            "raw_text": "",
            "report_type": "unknown",
            "values": {},
            "abnormal_count": 0,
            "critical_count": 0,
            "abnormal_values": {},
            "is_imaging_report": False,
            "is_prescription": False,
            "note": "Could not extract text. Please upload PDF or text file.",
        }

    # Step 2: Detect report type
    report_type = detect_report_type(raw_text)

    # Step 3: Extract quantitative values for lab report types
    values: dict = {}
    if report_type in REPORT_TYPE_RANGES:
        values = _extract_lab_values(raw_text, report_type)

    # Step 4: Classify abnormal / critical
    abnormal = {k: v for k, v in values.items() if v.get("flag") not in ("NORMAL", None)}
    critical  = {k: v for k, v in values.items() if "CRITICAL" in v.get("flag", "")}

    return {
        "raw_text": raw_text[:3000],
        "report_type": report_type,
        "values": values,
        "abnormal_count": len(abnormal),
        "critical_count": len(critical),
        "abnormal_values": abnormal,
        "is_imaging_report": report_type in ("xray_report", "mri_report", "ct_report"),
        "is_prescription": report_type == "prescription",
    }
