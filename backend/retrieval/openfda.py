import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
import httpx
from config import SOURCE_WEIGHTS

OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
FIELD_MAX_CHARS = 2000




def _extract_field(label: dict, field: str) -> str:
    value = label.get(field)
    if isinstance(value, list):
        return " ".join(str(v) for v in value)[:FIELD_MAX_CHARS]
    if isinstance(value, str):
        return value[:FIELD_MAX_CHARS]
    return ""


async def get_drug_info(drug_name: str) -> dict:
    """Fetch label information for a single drug from OpenFDA."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(OPENFDA_LABEL_URL, params={
                "search": (
                    f'openfda.brand_name:"{drug_name}"'
                    f' OR openfda.generic_name:"{drug_name}"'
                ),
                "limit": 1,
            })

            if resp.status_code == 404:
                return {"drug": drug_name, "found": False, "source": "OpenFDA"}

            resp.raise_for_status()
            results = resp.json().get("results", [])

            if not results:
                return {"drug": drug_name, "found": False, "source": "OpenFDA"}

            label = results[0]
            return {
                "drug": drug_name,
                "found": True,
                "warnings": _extract_field(label, "warnings"),
                "contraindications": _extract_field(label, "contraindications"),
                "drug_interactions": _extract_field(label, "drug_interactions"),
                "adverse_reactions": _extract_field(label, "adverse_reactions"),
                "dosage": _extract_field(label, "dosage_and_administration"),
                "source": "OpenFDA",
                "trust_weight": SOURCE_WEIGHTS.get("OpenFDA", 9),
            }
    except Exception as e:
        return {"drug": drug_name, "found": False, "error": str(e), "source": "OpenFDA"}


async def check_drug_interaction(drug1: str, drug2: str) -> dict:
    """Check for documented interaction between two drugs via OpenFDA label search."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(OPENFDA_LABEL_URL, params={
                "search": (
                    f'(openfda.brand_name:"{drug1}" OR openfda.generic_name:"{drug1}")'
                    f' AND drug_interactions:"{drug2}"'
                ),
                "limit": 1,
            })

        found_interaction = False
        interaction_details = ""

        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                found_interaction = True
                interaction_details = _extract_field(results[0], "drug_interactions")

        # Fetch individual drug info in parallel
        drug1_info, drug2_info = await asyncio.gather(
            get_drug_info(drug1),
            get_drug_info(drug2),
            return_exceptions=True,
        )
        if isinstance(drug1_info, Exception):
            drug1_info = {}
        if isinstance(drug2_info, Exception):
            drug2_info = {}

        return {
            "drug1": drug1,
            "drug2": drug2,
            "interaction_found": found_interaction,
            "interaction_details": (
                interaction_details[:FIELD_MAX_CHARS]
                if interaction_details
                else "No direct interaction data found in OpenFDA"
            ),
            "drug1_warnings": str(drug1_info.get("warnings", ""))[:1000],
            "drug2_warnings": str(drug2_info.get("warnings", ""))[:1000],
            "source": "OpenFDA",
            "trust_weight": SOURCE_WEIGHTS.get("OpenFDA", 9),
        }
    except Exception as e:
        return {
            "drug1": drug1,
            "drug2": drug2,
            "interaction_found": False,
            "error": str(e),
            "source": "OpenFDA",
        }
