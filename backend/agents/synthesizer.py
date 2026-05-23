import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import re
from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_MODEL

_client = None

def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client

DISCLAIMER = (
    "DISCLAIMER: This AI-generated analysis is for informational purposes only and does not constitute "
    "medical advice, diagnosis, or treatment. Always consult a qualified healthcare professional for "
    "medical decisions. In case of emergency, call 112 immediately."
)

SYNTHESIZER_PROMPT = """You are a senior clinician generating a differential diagnosis.
You have access to clinical pre-analysis and medical literature.

Patient Query: {query}
Patient Context: {patient_context}
Regional Context: {india_context}

Clinical Pre-Analysis (read this carefully):
{clinical_reasoning}

Medical Evidence Retrieved:
{evidence_summary}

YOUR TASK:
Generate the most clinically accurate differential diagnosis
by combining:
1. The pre-analysis reasoning
2. The retrieved medical evidence
3. Your clinical judgment

REASONING APPROACH:
- Start from the unifying hypothesis in pre-analysis
- Use evidence to confirm or refute it
- Consider the discriminating symptom when ranking
- The must-not-miss diagnosis goes in dangerous_differentials
- Confidence reflects how well evidence supports each diagnosis

TRIAGE RULES — be conservative, do NOT over-triage:

EMERGENCY (use very rarely):
  ONLY for: chest pain + breathlessness TOGETHER,
  unconscious/unresponsive, active seizure NOW,
  severe bleeding not stopping, stroke signs,
  anaphylaxis, infant not breathing
  → Must be immediately life-threatening RIGHT NOW

URGENT (use selectively):
  Fever >3 days AND worsening
  High fever in child >103F with other symptoms
  Dengue warning signs (bleeding, severe abdominal pain)
  Suspected malaria with high fever + chills
  Jaundice + fever together
  Diabetic with spreading infection
  Symptoms significantly impacting daily life
  → Needs doctor within 24 hours

ROUTINE (use for MOST queries):
  Fever <3 days, mild to moderate
  Common cold, cough, mild body ache
  Single symptom without red flags
  Known chronic condition, stable
  Child with mild fever, eating and drinking normally
  Most symptom queries without danger signs
  → Can wait 2-3 days, home care appropriate

INFORMATIONAL (use for):
  Drug questions, interactions
  General health questions
  Diet, lifestyle, prevention
  Asking about a condition in general
  No active symptoms
  → Educational, no urgent action needed

CRITICAL RULE:
Default to ROUTINE unless specific danger signs present.
Do NOT give URGENT just because symptoms are uncomfortable.
URGENT means the patient genuinely needs a doctor TODAY.
Most people with fever, body pain, headache = ROUTINE.
Dengue suspected in Mumbai monsoon = URGENT (specific reason).
Child with mild fever 2 days, eating normally = ROUTINE.

CONFIDENCE LOGIC:
High evidence match + common disease = 65-85%
Moderate evidence + fits pattern = 45-65%
Low evidence or atypical = 25-45%
Must-not-miss with weak evidence = 15-30%
Never exceed 85%

Return ONLY valid JSON:
{{
  "triage": "<EMERGENCY|URGENT|ROUTINE|INFORMATIONAL>",
  "conditions": [
    {{
      "name": "<diagnosis>",
      "confidence": <10-85>,
      "evidence": ["<specific evidence from retrieved papers>"],
      "reasoning": "<clinical reasoning tying this to patient symptoms>",
      "explains": "<which symptoms this diagnosis accounts for>"
    }}
  ],
  "immediate_actions": ["<specific actionable step>"],
  "recommended_tests": ["<specific test with reason>"],
  "drug_safety": {{
    "interactions_found": false,
    "warnings": [],
    "recommendations": []
  }},
  "red_flags": ["<seek emergency if: specific sign develops>"],
  "dangerous_differentials": ["<must-not-miss diagnosis>"],
  "follow_up_questions": [
    "{most_important_question}",
    "<second question that narrows diagnosis>"
  ],
  "patient_summary": "<2-3 sentences plain English covering all symptoms>",
  "clinical_reasoning_used": "{reasoning_summary}",
  "disclaimer": "{disclaimer}"
}}"""

FALLBACK = {
    "triage": "INFORMATIONAL",
    "conditions": [{"name": "Insufficient data", "confidence": 0, "evidence": ["Analysis could not be completed"]}],
    "immediate_actions": ["Please consult a qualified healthcare provider"],
    "recommended_tests": [],
    "drug_safety": {"interactions_found": False, "warnings": [], "recommendations": []},
    "red_flags": [],
    "follow_up_questions": ["Could you describe your symptoms in more detail?"],
    "patient_summary": "We were unable to complete a full analysis. Please consult a healthcare provider for a proper evaluation.",
    "disclaimer": DISCLAIMER,
}

def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError("No valid JSON in response")

def _build_evidence_summary(all_results: dict) -> str:
    parts = []
    pubmed = all_results.get("pubmed", [])
    if pubmed:
        parts.append("=== PubMed Research Articles ===")
        for i, article in enumerate(pubmed[:5]):
            if isinstance(article, dict) and "error" not in article:
                title = article.get("title", "No title")
                abstract = article.get("abstract", "")[:600]
                year = article.get("year", "n/d")
                pmid = article.get("pmid", "")
                parts.append(f"[{i+1}] {title} (PMID:{pmid}, {year})\n{abstract}")

    openfda = all_results.get("openfda", [])
    if openfda:
        parts.append("\n=== Drug Safety Data (OpenFDA) ===")
        for item in openfda[:3]:
            if not isinstance(item, dict):
                continue
            if "drug1" in item:
                parts.append(
                    f"Interaction check: {item.get('drug1')} + {item.get('drug2')}\n"
                    f"  Interaction found: {item.get('interaction_found', False)}\n"
                    f"  Details: {str(item.get('interaction_details', ''))[:400]}"
                )
            elif "drug" in item and item.get("found"):
                drug = item.get("drug", "")
                warnings = str(item.get("warnings", ""))[:400]
                interactions = str(item.get("drug_interactions", ""))[:400]
                parts.append(f"Drug: {drug}\n  Warnings: {warnings}\n  Interactions: {interactions}")

    return "\n\n".join(parts)[:5000] if parts else "No medical evidence was retrieved."

def _build_patient_context(patient_context: dict) -> str:
    if not patient_context:
        return "Not provided"
    parts = []
    if patient_context.get("age"):
        parts.append(f"Age: {patient_context['age']}")
    if patient_context.get("gender"):
        parts.append(f"Gender: {patient_context['gender']}")
    if patient_context.get("medications"):
        parts.append(f"Medications: {', '.join(patient_context['medications'])}")
    if patient_context.get("existing_conditions"):
        parts.append(f"Conditions: {', '.join(patient_context['existing_conditions'])}")
    return " | ".join(parts) if parts else "Not provided"

def _format_india_context(india_context: dict) -> str:
    if not india_context:
        return "General Indian clinical context."
    season = india_context.get("season", "unknown")
    high_risk = india_context.get("high_risk_diseases", [])
    note = india_context.get("epidemiological_note", "") or india_context.get("context_string", "")
    alerts = india_context.get("regional_alerts", [])

    parts = [f"Current season: {season}."]
    if high_risk:
        parts.append(f"High-risk diseases this season: {', '.join(high_risk[:3])}.")
    if alerts:
        alert_str = "; ".join(a.get("message", "") for a in alerts[:2] if a.get("message"))
        if alert_str:
            parts.append(f"Active alerts: {alert_str}.")
    if note:
        parts.append(note)
    return " ".join(parts)

def _format_clinical_reasoning(reasoning: dict) -> str:
    if not reasoning:
        return "No pre-analysis available."
    return (
        f"Pre-analysis summary: {reasoning.get('reasoning_summary', '')}\n"
        f"Discriminating symptom: {reasoning.get('discriminating_symptom', '')}\n"
        f"Unifying hypothesis: {reasoning.get('unifying_hypothesis', '')}\n"
        f"Primary system involved: {reasoning.get('primary_system', '')}\n"
        f"Must not miss: {reasoning.get('must_not_miss', '')}\n"
        f"Most important follow-up: {reasoning.get('most_important_question', '')}\n"
        f"Prior diagnoses considered: {json.dumps(reasoning.get('top_prior_diagnoses', []))}"
    )

def _validate_result(result: dict) -> dict:
    conditions = []
    for c in result.get("conditions", []):
        if isinstance(c, dict):
            conditions.append({
                "name": str(c.get("name", "Unknown")),
                "confidence": max(0, min(100, int(c.get("confidence", 0)))),
                "evidence": c.get("evidence", []) if isinstance(c.get("evidence"), list) else [],
                "reasoning": str(c.get("reasoning", "")),
                "explains": str(c.get("explains", "")),
            })
    result["conditions"] = conditions if conditions else FALLBACK["conditions"]
    result["disclaimer"] = DISCLAIMER
    result.setdefault("triage", "INFORMATIONAL")
    result.setdefault("immediate_actions", [])
    result.setdefault("recommended_tests", [])
    result.setdefault("drug_safety", {"interactions_found": False, "warnings": [], "recommendations": []})
    result.setdefault("red_flags", [])
    result.setdefault("dangerous_differentials", [])
    result.setdefault("follow_up_questions", [])
    result.setdefault("patient_summary", "Analysis complete. Please consult a healthcare provider.")
    result.setdefault("clinical_reasoning_used", "")
    return result


async def synthesize(
    query: str,
    all_results: dict,
    query_type: str,
    patient_context: dict,
    india_context: dict = {},
    clinical_reasoning: dict = {},
) -> dict:
    try:
        client = _get_client()
        most_important_q = clinical_reasoning.get(
            "most_important_question", "Can you describe your symptoms?"
        )
        reasoning_summary = clinical_reasoning.get("reasoning_summary", "")

        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{
                "role": "user",
                "content": SYNTHESIZER_PROMPT.format(
                    query=query,
                    patient_context=_build_patient_context(patient_context),
                    evidence_summary=_build_evidence_summary(all_results),
                    india_context=_format_india_context(india_context),
                    clinical_reasoning=_format_clinical_reasoning(clinical_reasoning),
                    most_important_question=most_important_q,
                    reasoning_summary=reasoning_summary,
                    disclaimer=DISCLAIMER,
                )
            }],
            temperature=0.3,
            max_tokens=1500,
        )
        raw = response.choices[0].message.content.strip()
        result = _parse_json(raw)
        return _validate_result(result)
    except Exception as e:
        return {**FALLBACK, "error": str(e)}
