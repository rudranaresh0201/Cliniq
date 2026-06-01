"""
ClinIQ 2.0 — pubmed_search tool.

Replaces the registry stub.  Two-step NCBI E-utilities flow:
  esearch → get WebEnv + query_key + id list
  efetch  → fetch XML abstracts, parse, score, return

No API key required; if NCBI_API_KEY is set it is forwarded for
higher rate limits (10 req/s vs 3 req/s for anonymous).
"""

import logging
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import httpx

from agents.tool_registry import REGISTRY, Tool

logger = logging.getLogger("cliniq.tools.pubmed_search")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_ESEARCH_URL = f"{_BASE_URL}/esearch.fcgi"
_EFETCH_URL = f"{_BASE_URL}/efetch.fcgi"
_PUBMED_ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

_DEFAULT_MAX_RESULTS = 5
_HTTP_TIMEOUT = 10.0  # seconds
_ABSTRACT_PREVIEW_CHARS = 500
_LAST_N_YEARS_DAYS = 1826  # ≈ 5 years

# Common English stop-words excluded from relevance scoring
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "of", "in", "on", "at", "to",
        "for", "with", "is", "are", "was", "were", "be", "been",
        "has", "have", "had", "by", "from", "as", "that", "this",
        "it", "its", "not", "but", "also",
    }
)

# ---------------------------------------------------------------------------
# Fallback response
# ---------------------------------------------------------------------------


def _fallback(error: str = "pubmed_unavailable") -> dict:
    return {"articles": [], "total_found": 0, "error": error}


# ---------------------------------------------------------------------------
# Shared HTTP params
# ---------------------------------------------------------------------------


def _base_params() -> dict:
    params: dict = {}
    api_key = os.environ.get("NCBI_API_KEY", "")
    if api_key:
        params["api_key"] = api_key
    return params


# ---------------------------------------------------------------------------
# Step 1 — esearch
# ---------------------------------------------------------------------------


async def _esearch(
    client: httpx.AsyncClient,
    query: str,
    max_results: int,
    india_filter: bool,
) -> tuple[str, str, list[str], int]:
    """
    Run esearch and return (webenv, query_key, id_list, total_count).
    Adds India MeSH filter and a 5-year date window when requested.
    """
    term = query
    if india_filter:
        term = f"{term} AND India[MeSH]"

    params = {
        **_base_params(),
        "db": "pubmed",
        "term": term,
        "retmax": str(max_results),
        "usehistory": "y",
        "retmode": "json",
        "reldate": str(_LAST_N_YEARS_DAYS),
        "datetype": "pdat",
    }

    resp = await client.get(_ESEARCH_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    result = data.get("esearchresult", {})
    webenv = result.get("webenv", "")
    query_key = result.get("querykey", "")
    id_list: list[str] = result.get("idlist", [])
    total_count = int(result.get("count", 0))

    logger.debug("esearch | term=%r | found=%d | returned=%d", term, total_count, len(id_list))
    return webenv, query_key, id_list, total_count


# ---------------------------------------------------------------------------
# Step 2 — efetch
# ---------------------------------------------------------------------------


async def _efetch(
    client: httpx.AsyncClient,
    webenv: str,
    query_key: str,
) -> str:
    """Fetch PubMed XML for the search result set stored in WebEnv."""
    params = {
        **_base_params(),
        "db": "pubmed",
        "query_key": query_key,
        "WebEnv": webenv,
        "rettype": "abstract",
        "retmode": "xml",
    }
    resp = await client.get(_EFETCH_URL, params=params)
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# XML parsing helpers
# ---------------------------------------------------------------------------


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _parse_year(article_node: ET.Element) -> int:
    year_el = article_node.find(
        "./Journal/JournalIssue/PubDate/Year"
    )
    if year_el is not None and year_el.text:
        try:
            return int(year_el.text)
        except ValueError:
            pass
    # Structured abstracts sometimes use MedlineDate like "2023 Jan-Feb"
    medline_el = article_node.find(
        "./Journal/JournalIssue/PubDate/MedlineDate"
    )
    if medline_el is not None and medline_el.text:
        match = re.search(r"\d{4}", medline_el.text)
        if match:
            return int(match.group())
    return 0


def _parse_abstract(article_node: ET.Element) -> str:
    """Join all AbstractText elements (handles structured abstracts)."""
    parts: list[str] = []
    for el in article_node.findall("./Abstract/AbstractText"):
        label = el.get("Label")
        text = "".join(el.itertext()).strip()
        if label:
            parts.append(f"{label}: {text}")
        elif text:
            parts.append(text)
    return " ".join(parts)


def _parse_first_author(article_node: ET.Element) -> str:
    author = article_node.find("./AuthorList/Author")
    if author is None:
        return "Unknown"
    last = _text(author.find("LastName"))
    fore = _text(author.find("ForeName"))
    initials = _text(author.find("Initials"))
    suffix = fore or initials
    return f"{last} {suffix}".strip() if last else "Unknown"


def _parse_doi(pubmed_data_node: ET.Element | None) -> str | None:
    if pubmed_data_node is None:
        return None
    for el in pubmed_data_node.findall("./ArticleIdList/ArticleId"):
        if el.get("IdType") == "doi":
            return el.text
    return None


# ---------------------------------------------------------------------------
# Step 3 — relevance scoring
# ---------------------------------------------------------------------------


def _query_keywords(query: str) -> set[str]:
    tokens = re.findall(r"[a-z]+", query.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 2}


def _score_relevance(title: str, abstract: str, keywords: set[str]) -> float:
    if not keywords:
        return 0.0
    haystack = (title + " " + abstract).lower()
    hits = sum(1 for kw in keywords if kw in haystack)
    return round(min(1.0, hits / len(keywords)), 3)


# ---------------------------------------------------------------------------
# Article parser — XML → list[dict]
# ---------------------------------------------------------------------------


def _parse_articles(xml_text: str, query_keywords_set: set[str]) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("efetch: XML parse error")
        return []

    articles: list[dict] = []
    for pub_article in root.findall("PubmedArticle"):
        citation = pub_article.find("MedlineCitation")
        if citation is None:
            continue

        pmid = _text(citation.find("PMID"))
        article_node = citation.find("Article")
        if article_node is None:
            continue

        title = _text(article_node.find("ArticleTitle"))
        abstract = _parse_abstract(article_node)
        first_author = _parse_first_author(article_node)
        journal = _text(article_node.find("./Journal/Title"))
        year = _parse_year(article_node)
        doi = _parse_doi(pub_article.find("PubmedData"))
        score = _score_relevance(title, abstract, query_keywords_set)

        articles.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract_preview": abstract[:_ABSTRACT_PREVIEW_CHARS],
                "first_author": first_author,
                "journal": journal,
                "year": year,
                "doi": doi,
                "relevance_score": score,
                "pubmed_url": _PUBMED_ARTICLE_URL.format(pmid=pmid),
            }
        )

    articles.sort(key=lambda a: a["relevance_score"], reverse=True)
    return articles


# ---------------------------------------------------------------------------
# Main tool function
# ---------------------------------------------------------------------------


async def search_pubmed(inputs: dict) -> dict:
    """
    Search PubMed for clinical evidence and return ranked abstracts.

    Uses NCBI E-utilities (esearch + efetch) and scores results by
    keyword overlap against the original query.
    """
    query: str = inputs.get("query", "")
    max_results: int = int(inputs.get("max_results", _DEFAULT_MAX_RESULTS))
    india_filter: bool = bool(inputs.get("india_filter", False))

    if not query.strip():
        logger.warning("search_pubmed called with empty query")
        return _fallback("empty_query")

    logger.info(
        "search_pubmed | query=%r | max=%d | india_filter=%s",
        query, max_results, india_filter,
    )

    keywords = _query_keywords(query)

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            webenv, query_key, id_list, total_found = await _esearch(
                client, query, max_results, india_filter
            )

            if not id_list:
                logger.info("search_pubmed: no results for query %r", query)
                return {"articles": [], "total_found": 0, "query_used": query}

            xml_text = await _efetch(client, webenv, query_key)

    except httpx.TimeoutException:
        logger.error("search_pubmed: NCBI request timed out")
        return _fallback()
    except httpx.HTTPStatusError as exc:
        logger.error("search_pubmed: HTTP %d from NCBI", exc.response.status_code)
        return _fallback()
    except Exception:
        logger.exception("search_pubmed: unexpected error")
        return _fallback()

    articles = _parse_articles(xml_text, keywords)

    # Reflect india filter in returned query string
    query_used = f"{query} AND India[MeSH]" if india_filter else query

    logger.info(
        "search_pubmed OK | returned=%d | total_found=%d",
        len(articles), total_found,
    )
    return {
        "articles": articles,
        "total_found": total_found,
        "query_used": query_used,
    }


# ---------------------------------------------------------------------------
# Re-register with real implementation
# ---------------------------------------------------------------------------

REGISTRY.register(
    Tool(
        name="pubmed_search",
        description="Search PubMed for clinical evidence on a topic",
        input_schema={
            "type": "object",
            "properties": {
                "query":        {"type": "string"},
                "max_results":  {"type": "integer"},
                "india_filter": {"type": "boolean"},
            },
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "articles":    {"type": "array"},
                "total_found": {"type": "integer"},
                "query_used":  {"type": "string"},
            },
        },
        agent="research_agent",
        async_fn=search_pubmed,
    )
)

logger.debug("pubmed_search: real implementation registered")
