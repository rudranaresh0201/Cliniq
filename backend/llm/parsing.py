"""
Shared JSON extraction helpers for LLM response parsing.
"""

import re
import json


def extract_json(text: str) -> str:
    """
    Extract the first valid JSON object from LLM output.
    Handles: ```json fences, ``` fences, leading markdown, trailing text.
    """
    if not text:
        raise ValueError("Empty response")

    # Strip ```json ... ``` or ``` ... ``` fences
    fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if fenced:
        return fenced.group(1)

    # Scan from first { to last } (outermost JSON object)
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]

    raise ValueError("No JSON object found in response")


def fix_json(raw: str) -> str:
    """Fix common LLM JSON issues before parsing."""
    # Remove trailing commas before } or ]
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    # Remove single-line comments
    raw = re.sub(r'//.*?\n', '\n', raw)
    return raw


def parse_llm_json(text: str) -> dict:
    """Extract, fix, and parse JSON from LLM output. Raises on failure."""
    extracted = extract_json(text)
    fixed = fix_json(extracted)
    return json.loads(fixed)
