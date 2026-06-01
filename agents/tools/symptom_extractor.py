"""
ClinIQ 2.0 — symptom_extractor tool.

Replaces the registry stub.  Accepts free text in English, Hindi, or
Hinglish and uses Groq (llama-3.3-70b-versatile) to return a structured
JSON symptom object that downstream clinical tools can consume directly.
"""

import json
import logging
import os

from groq import AsyncGroq

from agents.tool_registry import REGISTRY, Tool

logger = logging.getLogger("cliniq.tools.symptom_extractor")

_GROQ_MODEL = "llama-3.3-70b-versatile"

# ---------------------------------------------------------------------------
# System prompt — embedded exactly as specified
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a clinical symptom extractor for an Indian medical AI.
Extract symptoms from the patient's text precisely.

The patient may write in English, Hindi, or Hinglish.
Common Hindi medical terms to recognize:
- bukhar/tez bukhar = fever
- dard = pain
- sar dard = headache
- pet dard = abdominal pain
- khasi = cough
- saans lena mushkil = difficulty breathing
- ulti/vomiting = vomiting
- dast = diarrhea
- thakaan = fatigue
- bhook nahi = loss of appetite
- jodon mein dard = joint pain
- sar ghoomna = dizziness
- aankhon mein peelaahat = yellow eyes (jaundice)
- pasina = sweating
- kaanpna = chills

Return ONLY a valid JSON object, no markdown:
{
  "symptoms": [
    {
      "name": "symptom name in English",
      "severity": "mild|moderate|severe",
      "duration": "e.g. 3 days, 1 week",
      "body_system": "respiratory|gastrointestinal|neurological|musculoskeletal|cardiovascular|dermatological|genitourinary|constitutional|ophthalmological|other",
      "original_text": "exact phrase patient used"
    }
  ],
  "overall_duration": "how long patient has been sick overall",
  "primary_complaint": "the single most important symptom",
  "red_flags": ["any immediately concerning symptoms"],
  "language_detected": "en|hi|hinglish",
  "confidence": 0.0 to 1.0
}"""

_REQUIRED_FIELDS = {
    "symptoms",
    "overall_duration",
    "primary_complaint",
    "red_flags",
    "language_detected",
    "confidence",
}

# ---------------------------------------------------------------------------
# Groq client — initialised lazily so missing keys surface at call time,
# not at import time (allows the module to load in test environments).
# ---------------------------------------------------------------------------

_groq_client: AsyncGroq | None = None


def _get_groq() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY environment variable is not set")
        _groq_client = AsyncGroq(api_key=api_key)
    return _groq_client


# ---------------------------------------------------------------------------
# Fallback response
# ---------------------------------------------------------------------------


def _fallback(text: str, language: str, error: str) -> dict:
    return {
        "symptoms": [],
        "primary_complaint": text[:100],
        "overall_duration": "unknown",
        "red_flags": [],
        "language_detected": language,
        "confidence": 0.0,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Main tool function
# ---------------------------------------------------------------------------


async def extract_symptoms(inputs: dict) -> dict:
    """
    Extract structured symptoms from free-text patient input.

    Accepts English, Hindi, and Hinglish.  Returns a dict that matches
    the tool's declared output_schema and can be consumed directly by
    clinical_reasoner and india_epidemiology_reranker.
    """
    text: str = inputs.get("text", "")
    language: str = inputs.get("language", "en")

    if not text.strip():
        logger.warning("extract_symptoms called with empty text")
        return _fallback(text, language, "empty_input")

    logger.info(
        "extract_symptoms | language=%s | text_len=%d", language, len(text)
    )

    try:
        raw = await _call_groq(text, language)
    except Exception:
        logger.exception("extract_symptoms: Groq call failed")
        return _fallback(text, language, "extraction_failed")

    try:
        result = _parse_and_validate(raw)
    except Exception:
        logger.exception(
            "extract_symptoms: JSON parse/validation failed | raw=%s", raw[:200]
        )
        return _fallback(text, language, "extraction_failed")

    print(f"SYMPTOMS OUT: {result}")
    logger.info(
        "extract_symptoms OK | symptoms=%d | confidence=%.2f | lang=%s",
        len(result.get("symptoms", [])),
        result.get("confidence", 0.0),
        result.get("language_detected", language),
    )
    return result


async def _call_groq(text: str, language: str) -> str:
    """Send the extraction request to Groq and return the raw content string."""
    user_message = f"Language hint: {language}\n\nPatient text:\n{text}"
    response = await _get_groq().chat.completions.create(
        model=_GROQ_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


def _parse_and_validate(raw: str) -> dict:
    """Strip accidental markdown fences, parse JSON, assert required fields."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        # parts[1] is the fenced block; strip a leading 'json' language tag
        cleaned = parts[1].lstrip("json").strip()

    data: dict = json.loads(cleaned)

    missing = _REQUIRED_FIELDS - data.keys()
    if missing:
        raise ValueError(f"Response missing required fields: {missing}")

    # Coerce confidence to float in [0, 1]
    data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))

    return data


# ---------------------------------------------------------------------------
# Re-register with the real implementation
# Importing this module replaces the stub that tool_registry.py registered
# at startup.
# ---------------------------------------------------------------------------

REGISTRY.register(
    Tool(
        name="symptom_extractor",
        description="Extract structured symptoms from free text or voice transcript",
        input_schema={
            "type": "object",
            "properties": {
                "text":     {"type": "string"},
                "language": {"type": "string"},
            },
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "symptoms":          {"type": "array"},
                "overall_duration":  {"type": "string"},
                "primary_complaint": {"type": "string"},
                "red_flags":         {"type": "array"},
                "language_detected": {"type": "string"},
                "confidence":        {"type": "number"},
            },
        },
        agent="clinical_agent",
        async_fn=extract_symptoms,
    )
)

logger.debug("symptom_extractor: real implementation registered")
