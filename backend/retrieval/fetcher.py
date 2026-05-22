import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
from backend.retrieval.pubmed import search_pubmed
from backend.retrieval.openfda import check_drug_interaction, get_drug_info
from config import MAX_SEARCH_RESULTS

# Query types that warrant drug interaction pairwise checks
INTERACTION_CHECK_TYPES = {"drug_interaction", "emergency", "diagnosis_support"}


async def fetch_all(
    queries: list[str],
    query_type: str,
    drugs: list[str] | None = None,
) -> dict:
    """
    Run all PubMed searches and OpenFDA drug checks concurrently.
    Returns merged results keyed by source type.
    """
    if drugs is None:
        drugs = []

    tasks: list = []
    labels: list[tuple[str, str]] = []

    # One PubMed search per query
    for q in queries:
        tasks.append(search_pubmed(q, MAX_SEARCH_RESULTS))
        labels.append(("pubmed", q))

    # Drug checks
    if drugs:
        if query_type in INTERACTION_CHECK_TYPES and len(drugs) >= 2:
            # Pairwise interaction checks
            for i in range(len(drugs)):
                for j in range(i + 1, len(drugs)):
                    tasks.append(check_drug_interaction(drugs[i], drugs[j]))
                    labels.append(("drug_interaction", f"{drugs[i]}+{drugs[j]}"))
        else:
            # Individual drug info
            for drug in drugs:
                tasks.append(get_drug_info(drug))
                labels.append(("drug_info", drug))

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    pubmed_results: list[dict] = []
    openfda_results: list[dict] = []

    for (result_type, _label), result in zip(labels, raw_results):
        if isinstance(result, Exception):
            continue
        if result_type == "pubmed" and isinstance(result, list):
            pubmed_results.extend(result)
        elif result_type in ("drug_interaction", "drug_info") and isinstance(result, dict):
            openfda_results.append(result)

    return {
        "pubmed": pubmed_results,
        "openfda": openfda_results,
        "total_sources": len(pubmed_results) + len(openfda_results),
    }
