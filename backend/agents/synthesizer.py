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

SYNTHESIZER_PROMPT = """You are a senior Indian general physician with 15 years of clinical experience in urban India.
You think like a real doctor, not a medical textbook.

Patient Query: {query}
Query Type: {query_type}
Patient Context: {patient_context}
India Clinical Context: {india_context}

Medical Evidence:
{evidence_summary}

TRIAGE RULES — follow strictly:
EMERGENCY: chest pain + breathlessness, unconscious, stroke signs,
  severe bleeding, anaphylaxis, child with seizure NOW
  → patient must go to hospital immediately

URGENT: symptoms for 3+ days worsening, high fever >103F in child,
  dengue warning signs (bleeding, severe pain), suspected malaria,
  diabetic with infection, jaundice with fever
  → see doctor today or tomorrow

ROUTINE: mild fever < 3 days, common cold, minor infections,
  known chronic condition stable, asking about medications
  → can wait 2-3 days, home care first

INFORMATIONAL: general health questions, drug information,
  diet queries, preventive health
  → no urgent action needed

INDIA CLINICAL REALITY — think like this:
- Fever + body pain + rash in Mumbai monsoon = dengue first
- Fever + chills + sweating = malaria until proven otherwise
- Fever + vomiting + loose stools = gastroenteritis or typhoid
- Child fever for 2 days = viral fever most likely
- Cough + fever + weight loss = TB must be considered
- Fever + headache in child = viral first, meningitis only if
  neck stiffness or photophobia mentioned
- Joint pain + rash + fever = chikungunya or dengue
- Jaundice + fever = hepatitis A/E or leptospirosis

CONFIDENCE CALIBRATION:
- Viral fever for generic fever symptoms: 70-80%
- Dengue in monsoon Mumbai with rash: 75-85%
- Malaria with periodic fever + chills: 70-80%
- Meningitis with only fever + headache (no neck stiffness): MAX 20%
- Any rare disease with generic symptoms: MAX 25%
- Never exceed 85% for any condition
- If symptoms are very mild and short duration → lower confidence

CONDITIONS RULES:
- List maximum 3-4 conditions
- Common Indian diseases MUST dominate for generic symptoms
- Rare conditions only if patient has SPECIFIC symptoms for them
- Order by confidence descending

DANGEROUS CONDITIONS RULE:
- Meningitis, encephalitis, intracranial abscess, myocarditis
- These go in dangerous_differentials[] NOT in conditions[]
- EXCEPTION: only put in conditions[] if patient has specific signs
  (neck stiffness, photophobia, focal neurology, altered consciousness)
- Always mention them in red_flags[] as "seek emergency if..."

Return ONLY valid JSON — no markdown, no explanation:
{{
  "triage": "<EMERGENCY|URGENT|ROUTINE|INFORMATIONAL>",
  "conditions": [
    {{
      "name": "<condition name>",
      "confidence": <integer 10-85>,
      "evidence": ["<specific evidence>"],
      "reasoning": "<one line clinical reasoning>"
    }}
  ],
  "immediate_actions": ["<specific action>"],
  "recommended_tests": ["<specific test>"],
  "drug_safety": {{
    "interactions_found": false,
    "warnings": [],
    "recommendations": []
  }},
  "red_flags": ["<go to hospital immediately if: specific sign>"],
  "dangerous_differentials": ["<serious condition to rule out>"],
  "follow_up_questions": ["<question to help narrow diagnosis>"],
  "patient_summary": "<plain English, reassuring but honest, 2-3 sentences>",
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


def _validate_result(result: dict) -> dict:
    conditions = []
    for c in result.get("conditions", []):
        if isinstance(c, dict):
            conditions.append({
                "name": str(c.get("name", "Unknown")),
                "confidence": max(0, min(100, int(c.get("confidence", 0)))),
                "evidence": c.get("evidence", []) if isinstance(c.get("evidence"), list) else [],
                "reasoning": str(c.get("reasoning", "")),
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
    return result


async def synthesize(
    query: str,
    all_results: dict,
    query_type: str,
    patient_context: dict,
    india_context: dict = {},
) -> dict:
    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{
                "role": "user",
                "content": SYNTHESIZER_PROMPT.format(
                    query=query,
                    query_type=query_type,
                    patient_context=_build_patient_context(patient_context),
                    evidence_summary=_build_evidence_summary(all_results),
                    india_context=_format_india_context(india_context),
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
