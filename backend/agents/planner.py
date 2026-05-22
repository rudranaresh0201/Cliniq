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

PLANNER_PROMPT = """You are a medical search strategist. Given a medical query and its classification, decide the optimal search strategy.

Query: {query}
Query Type: {query_type}
Classification: {classification}

Return ONLY a valid JSON object with these exact fields:
{{
  "searches": ["<search term 1>", "<search term 2>", "<search term 3>"],
  "drugs_to_check": ["<drug name 1>", "<drug name 2>"],
  "strategy": "<one-line strategy description>",
  "reasoning": "<why this approach>"
}}

Rules:
- Maximum 3 search queries in the searches array
- For drug_interaction: include drug names in both searches and drugs_to_check
- For emergency: prioritize clinical treatment guidelines
- For symptoms: include differential diagnosis terminology
- For research: use MeSH terms and clinical language
- drugs_to_check should be empty [] if no medications are mentioned
- Use precise medical terminology in search queries"""

FALLBACK = {
    "searches": [],
    "drugs_to_check": [],
    "strategy": "direct_query",
    "reasoning": "Planning unavailable, using original query",
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

async def plan_search(query: str, query_type: str, classification: dict) -> dict:
    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{
                "role": "user",
                "content": PLANNER_PROMPT.format(
                    query=query,
                    query_type=query_type,
                    classification=json.dumps(classification, indent=2)
                )
            }],
            temperature=0.2,
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()
        result = _parse_json(raw)

        searches = result.get("searches", [])
        if not searches:
            searches = [query]

        return {
            "searches": searches[:3],
            "drugs_to_check": result.get("drugs_to_check", []),
            "strategy": result.get("strategy", "direct_query"),
            "reasoning": result.get("reasoning", ""),
        }
    except Exception as e:
        return {**FALLBACK, "searches": [query], "error": str(e)}
