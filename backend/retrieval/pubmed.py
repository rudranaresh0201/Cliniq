import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import xml.etree.ElementTree as ET
import httpx
from config import MAX_SEARCH_RESULTS, SOURCE_WEIGHTS

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ABSTRACT_MAX_CHARS = 2000


async def search_pubmed(query: str, max_results: int | None = None) -> list[dict]:
    """Search PubMed via NCBI E-utilities and return parsed article records."""
    if max_results is None:
        max_results = MAX_SEARCH_RESULTS

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: get PMIDs ranked by relevance
            search_resp = await client.get(ESEARCH_URL, params={
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
                "sort": "relevance",
            })
            search_resp.raise_for_status()
            pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])

            if not pmids:
                return []

            # Step 2: fetch full abstracts for those PMIDs
            fetch_resp = await client.get(EFETCH_URL, params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
                "rettype": "abstract",
            })
            fetch_resp.raise_for_status()
            return _parse_pubmed_xml(fetch_resp.text)

    except Exception as e:
        return [{"error": str(e), "source": "PubMed"}]


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    results = []
    try:
        root = ET.fromstring(xml_text)
        for article_node in root.findall(".//PubmedArticle"):
            try:
                record = _parse_article(article_node)
                if record:
                    results.append(record)
            except Exception:
                continue
    except ET.ParseError:
        pass
    return results


def _parse_article(node) -> dict | None:
    pmid_el = node.find(".//PMID")
    pmid = pmid_el.text.strip() if pmid_el is not None and pmid_el.text else "unknown"

    title_el = node.find(".//ArticleTitle")
    title = "".join(title_el.itertext()).strip() if title_el is not None else "No title"

    abstract_els = node.findall(".//AbstractText")
    if abstract_els:
        abstract = " ".join("".join(el.itertext()).strip() for el in abstract_els)
    else:
        abstract = "No abstract available"
    abstract = abstract[:ABSTRACT_MAX_CHARS]

    # Year: prefer <Year>, fall back to MedlineDate (first 4 chars)
    year_el = node.find(".//PubDate/Year")
    if year_el is None:
        year_el = node.find(".//PubDate/MedlineDate")
    year = (year_el.text or "")[:4] if year_el is not None else "unknown"

    return {
        "title": title,
        "abstract": abstract,
        "pmid": pmid,
        "year": year,
        "source": "PubMed",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "trust_weight": SOURCE_WEIGHTS.get("PubMed", 8),
    }
