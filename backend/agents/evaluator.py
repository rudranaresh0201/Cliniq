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

EVALUATOR_PROMPT = """You are a medical evidence evaluator. Assess whether the retrieved data is sufficient to answer the query confidently.

Query: {query}
Retrieval Attempt: {attempt} of 3

Retrieved Evidence:
- PubMed Articles Found: {pubmed_count}
- OpenFDA Drug Records: {openfda_count}
- Key Findings:
{findings_summary}

Return ONLY a valid JSON object with these exact fields:
{{
  "confident": <true or false>,
  "confidence_score": <float between 0.0 and 1.0>,
  "missing": "<what critical information is still needed, or empty string if sufficient>",
  "refined_query": "<a more specific search query to fill the gap, or empty string if not needed>"
}}

Set confident=true only when confidence_score >= 0.75.
Evaluate based on: evidence relevance, completeness, clinical specificity, and source quality.
If pubmed_count is 0 and openfda_count is 0, confidence_score must be below 0.4."""

FALLBACK = {
    "confident": True,
    "confidence_score": 0.75,
    "missing": "",
    "refined_query": "",
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

def _summarize_findings(retrieved: dict) -> str:
    parts = []
    for article in retrieved.get("pubmed", [])[:3]:
        if isinstance(article, dict) and "error" not in article:
            title = article.get("title", "")[:100]
            year = article.get("year", "")
            parts.append(f"  • [{year}] {title}")
    for item in retrieved.get("openfda", [])[:2]:
        if isinstance(item, dict) and "error" not in item:
            if "drug1" in item:
                found = item.get("interaction_found", False)
                parts.append(f"  • Drug interaction {item['drug1']}+{item['drug2']}: {'found' if found else 'not found'}")
            elif "drug" in item:
                parts.append(f"  • Drug info for {item['drug']}: {'found' if item.get('found') else 'not found'}")
    return "\n".join(parts) if parts else "  • No relevant data retrieved"

async def evaluate(query: str, retrieved: dict, attempt: int) -> dict:
    try:
        client = _get_client()
        pubmed_count = len(retrieved.get("pubmed", []))
        openfda_count = len(retrieved.get("openfda", []))

        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{
                "role": "user",
                "content": EVALUATOR_PROMPT.format(
                    query=query,
                    attempt=attempt,
                    pubmed_count=pubmed_count,
                    openfda_count=openfda_count,
                    findings_summary=_summarize_findings(retrieved)
                )
            }],
            temperature=0.1,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        result = _parse_json(raw)

        score = float(result.get("confidence_score", 0.5))
        return {
            "confident": score >= 0.75,
            "confidence_score": score,
            "missing": result.get("missing", ""),
            "refined_query": result.get("refined_query", ""),
        }
    except Exception as e:
        return {**FALLBACK, "error": str(e)}
