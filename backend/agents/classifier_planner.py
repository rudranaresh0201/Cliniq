import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.llm.router import complete, parse_json

COMBINED_PROMPT = """You are a medical query analyst and search strategist.

Patient Query: {query}
Patient Context: {patient_context}

In ONE response, do two things:

1. CLASSIFY: What type of query is this?
Types: emergency, drug_interaction, symptoms,
       outbreak, diagnosis_support, research, general

2. PLAN: What should we search for?
Generate 3 targeted PubMed search queries.
For symptoms: include differential diagnosis terms.
For drug queries: include drug names + "interaction".
For India queries: include India-specific terms.

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
) -> dict:
    """Single LLM call replacing separate classify_query + plan_search calls."""
    if patient_context is None:
        patient_context = {}

    context_str = (
        f"Age: {patient_context.get('age', 'unknown')}, "
        f"State: {patient_context.get('state', 'Maharashtra')}"
    )

    try:
        raw, _ = await complete(
            COMBINED_PROMPT.format(query=query, patient_context=context_str),
            temperature=0.15,
            max_tokens=400,
        )
        result = parse_json(raw)

        if not result.get("searches"):
            result["searches"] = [query]
        result["searches"] = result["searches"][:3]

        # Ensure all required keys are present
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
