import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import re
from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_MODEL, QUERY_TYPES

_client = None

def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client

CLASSIFICATION_PROMPT = """You are a medical query classifier. Classify the given medical query into exactly one type.

Available types: {query_types}

Return ONLY a valid JSON object with these exact fields:
{{
  "query_type": "<one of the query types above>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<brief one-sentence explanation>",
  "priority_sources": ["<source1>", "<source2>"],
  "requires_drug_check": <true or false>
}}

Priority sources must be chosen from: PubMed, OpenFDA, CDC, WHO, MedlinePlus

Query to classify: {query}"""

FALLBACK = {
    "query_type": "general",
    "confidence": 0.5,
    "reasoning": "Classification unavailable, defaulting to general",
    "priority_sources": ["PubMed"],
    "requires_drug_check": False,
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

async def classify_query(query: str) -> dict:
    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{
                "role": "user",
                "content": CLASSIFICATION_PROMPT.format(
                    query_types=", ".join(QUERY_TYPES),
                    query=query
                )
            }],
            temperature=0.1,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        result = _parse_json(raw)

        if result.get("query_type") not in QUERY_TYPES:
            result["query_type"] = "general"

        return {
            "query_type": result.get("query_type", "general"),
            "confidence": float(result.get("confidence", 0.5)),
            "reasoning": result.get("reasoning", ""),
            "priority_sources": result.get("priority_sources", ["PubMed"]),
            "requires_drug_check": bool(result.get("requires_drug_check", False)),
        }
    except Exception as e:
        return {**FALLBACK, "error": str(e)}
