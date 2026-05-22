import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from rank_bm25 import BM25Okapi

logger = logging.getLogger("cliniq")


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _reciprocal_rank_fusion(
    bm25_ranking: list[int],
    dense_ranking: list[int],
    k: int = 60,
) -> list[tuple[int, float]]:
    """
    Merge two ranked lists of document indices using Reciprocal Rank Fusion.
    Returns list of (index, score) sorted descending by score.
    """
    scores: dict[int, float] = {}

    for rank, idx in enumerate(bm25_ranking):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)

    for rank, idx in enumerate(dense_ranking):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def hybrid_search(
    query: str,
    documents: list[str],
    top_k: int = 5,
    dense_scores: list[float] | None = None,
) -> list[str]:
    """
    Combine BM25 keyword search with optional dense similarity scores using RRF.

    Args:
        query: The search query string.
        documents: Corpus of document strings to search over.
        top_k: Number of results to return.
        dense_scores: Pre-computed cosine similarity scores (same length as documents).
                      If None, falls back to BM25-only ranking.

    Returns:
        List of top_k document strings, best-first.
    """
    if not documents:
        return []

    top_k = min(top_k, len(documents))

    # BM25 ranking
    tokenized_corpus = [_tokenize(d) for d in documents]
    bm25 = BM25Okapi(tokenized_corpus)
    bm25_scores = bm25.get_scores(_tokenize(query))
    bm25_ranking = sorted(range(len(documents)), key=lambda i: bm25_scores[i], reverse=True)

    if dense_scores is None:
        # BM25 only
        return [documents[i] for i in bm25_ranking[:top_k]]

    # Dense ranking from pre-computed scores
    dense_ranking = sorted(range(len(documents)), key=lambda i: dense_scores[i], reverse=True)

    fused = _reciprocal_rank_fusion(bm25_ranking, dense_ranking)
    return [documents[idx] for idx, _ in fused[:top_k]]
