import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.llm.router import complete, parse_json

REASONING_PROMPT = """You are a world-class diagnostician.
Your job is to reason deeply about this patient's presentation
before anyone generates a differential diagnosis.

Patient: {query}
Context: {patient_context}
Region: {india_context}

Think through this systematically:

STEP 1 — SYMPTOM INVENTORY
List every symptom mentioned explicitly.
List every symptom implied by context.
Note: duration, severity, progression, onset.

STEP 2 — PATTERN RECOGNITION
What symptom COMBINATION is most clinically significant?
Which symptom is most discriminating (narrows diagnosis most)?
Which symptom is most specific (not just common)?
What symptom would most change your diagnosis if absent?

STEP 3 — UNIFYING HYPOTHESIS
What single diagnosis could explain ALL symptoms together?
What body system is most likely involved?
Is this primarily infectious, endocrine, autoimmune,
structural, metabolic, or psychological?

STEP 4 — PRIOR PROBABILITY
Given: patient age, gender, region, season
What are the top 5 most likely diagnoses BEFORE evidence?
What is the base rate of each in this population?

STEP 5 — EVIDENCE REQUIREMENTS
What specific evidence would CONFIRM each diagnosis?
What evidence would RULE OUT each diagnosis?
What is the single most important test to order?

STEP 6 — RED FLAG ASSESSMENT
What dangerous diagnosis MUST be ruled out even if unlikely?
What symptom combination would make this an emergency?
Is anything time-sensitive here?

Return ONLY valid JSON:
{{
  "discriminating_symptom": "<most specific/unusual symptom>",
  "unifying_hypothesis": "<single best explanation for ALL symptoms>",
  "primary_system": "<body system most involved>",
  "clinical_pattern": "<name of the pattern: e.g. fever-arthralgia-rash triad>",
  "top_prior_diagnoses": [
    {{
      "name": "<diagnosis>",
      "prior_probability": "<high/medium/low>",
      "key_supporting_feature": "<why this fits>"
    }}
  ],
  "must_not_miss": "<dangerous diagnosis to rule out>",
  "most_important_question": "<single follow-up that changes diagnosis most>",
  "most_important_test": "<single most discriminating test>",
  "reasoning_confidence": "<high/medium/low>",
  "reasoning_summary": "<2-3 sentence clinical reasoning narrative>"
}}"""

FALLBACK = {
    "discriminating_symptom": "",
    "unifying_hypothesis": "insufficient information",
    "primary_system": "general",
    "clinical_pattern": "undifferentiated",
    "top_prior_diagnoses": [],
    "must_not_miss": "",
    "most_important_question": "Can you describe your symptoms in more detail?",
    "most_important_test": "Complete blood count",
    "reasoning_confidence": "low",
    "reasoning_summary": "Clinical reasoning unavailable.",
}


async def reason_clinically(
    query: str,
    patient_context: dict,
    india_context: dict,
) -> dict:
    context_str = (
        f"Age: {patient_context.get('age', 'unknown')}, "
        f"Gender: {patient_context.get('gender', 'unknown')}, "
        f"Medications: {patient_context.get('medications', [])}, "
        f"Existing conditions: {patient_context.get('existing_conditions', [])}"
    )
    india_str = india_context.get("context_string", "")

    try:
        raw, _ = await complete(
            REASONING_PROMPT.format(
                query=query,
                patient_context=context_str,
                india_context=india_str,
            ),
            temperature=0.2,
            max_tokens=800,
        )
        return parse_json(raw)
    except Exception as e:
        return {**FALLBACK, "error": str(e)}
