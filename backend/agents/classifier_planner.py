import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
from backend.llm.router import complete, parse_json

COMBINED_PROMPT = """You are a medical query analyst and search strategist.

Patient Query: {query}
Patient Context: {patient_context}

Clinical Pre-Analysis:
{clinical_reasoning}

The clinical reasoner has identified:
- Discriminating symptom: {discriminating_symptom}
- Unifying hypothesis: {unifying_hypothesis}
- Primary body system: {primary_system}
- Must not miss: {must_not_miss}

In ONE response, do two things:

1. CLASSIFY: What type of query is this?
Types: emergency, drug_interaction, symptoms,
       outbreak, diagnosis_support, research, general

2. PLAN: Generate 3 highly targeted PubMed search queries.
Search 1: Target the unifying hypothesis directly
Search 2: Target the discriminating symptom + patient context
Search 3: Target the must-not-miss diagnosis
Do NOT generate generic searches if specific ones are possible.

Return ONLY valid JSON:
{{
  "query_type": "<type>",
  "confidence": <float 0-1>,
  "requires_drug_check": <bool>,
  "priority_sources": ["PubMed", "OpenFDA"],
  "searches": ["<search 1>", "<search 2>", "<search 3>"],
  "drugs_to_check": ["<drug if applicable>"],
  "strategy": "<one line strategy>",
  "reasoning": "<why this approach>"
}}"""

FALLBACK = {
    "query_type": "general",
    "confidence": 0.5,
    "requires_drug_check": False,
    "priority_sources": ["PubMed"],
    "searches": [],
    "drugs_to_check": [],
    "strategy": "direct_query",
    "reasoning": "Fallback: combined classifier-planner failed",
}


async def classify_and_plan(
    query: str,
    patient_context: dict | None = None,
    clinical_reasoning: dict | None = None,
) -> dict:
    """Single LLM call: classifies query and plans evidence searches,
    informed by clinical pre-analysis when available."""
    if patient_context is None:
        patient_context = {}
    if clinical_reasoning is None:
        clinical_reasoning = {}

    context_str = (
        f"Age: {patient_context.get('age', 'unknown')}, "
        f"State: {patient_context.get('state', 'Maharashtra')}"
    )

    reasoning_summary = clinical_reasoning.get("reasoning_summary", "Not available")
    discriminating = clinical_reasoning.get("discriminating_symptom", "")
    hypothesis = clinical_reasoning.get("unifying_hypothesis", "")
    system = clinical_reasoning.get("primary_system", "general")
    must_not_miss = clinical_reasoning.get("must_not_miss", "")

    try:
        raw, _ = await complete(
            COMBINED_PROMPT.format(
                query=query,
                patient_context=context_str,
                clinical_reasoning=reasoning_summary,
                discriminating_symptom=discriminating,
                unifying_hypothesis=hypothesis,
                primary_system=system,
                must_not_miss=must_not_miss,
            ),
            temperature=0.15,
            max_tokens=400,
        )
        result = parse_json(raw)

        if not result.get("searches"):
            result["searches"] = [query]
        result["searches"] = result["searches"][:3]

        result.setdefault("query_type", "general")
        result.setdefault("confidence", 0.5)
        result.setdefault("requires_drug_check", False)
        result.setdefault("priority_sources", ["PubMed"])
        result.setdefault("drugs_to_check", [])
        result.setdefault("strategy", "direct_query")
        result.setdefault("reasoning", "")

        return result
    except Exception as e:
        return {**FALLBACK, "searches": [query], "reasoning": f"Fallback: {e}"}
