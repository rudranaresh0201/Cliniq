import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import logging
import chromadb
from sentence_transformers import SentenceTransformer
from config import (
    CHROMA_PATH,
    CHROMA_COLLECTION,
    EMBEDDING_MODEL,
    SIMILARITY_THRESHOLD,
    TTL_GUIDELINES,
    TTL_DRUG_ALERTS,
    TTL_PAPERS,
)

logger = logging.getLogger("cliniq")

# Maps source_type strings to their TTL in seconds
TTL_MAP: dict[str, float] = {
    "guidelines": TTL_GUIDELINES,
    "drug_alerts": TTL_DRUG_ALERTS,
    "papers": TTL_PAPERS,
    "pubmed": TTL_PAPERS,
    "openfda": TTL_DRUG_ALERTS,
    "general": TTL_GUIDELINES,
}

_chroma_client = None
_collection = None
_embed_model = None


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _chroma_client.get_or_create_collection(
            name=CHROMA_COLLECTION,
        )
    return _collection


def reset_collection_if_model_changed():
    """
    Checks if embedding model changed.
    If yes, clears ChromaDB collection.
    Old vectors from a different model produce wrong similarity scores.
    """
    global _chroma_client, _collection
    try:
        collection = _get_collection()
        metadata = collection.metadata or {}
        stored_model = metadata.get("embedding_model", "")
        current_model = EMBEDDING_MODEL

        if stored_model and stored_model != current_model:
            logger.warning(
                f"Embedding model changed from {stored_model} "
                f"to {current_model}. Clearing collection."
            )
            _chroma_client.delete_collection(CHROMA_COLLECTION)
            _chroma_client.create_collection(
                name=CHROMA_COLLECTION,
                metadata={
                    "hnsw:space": "cosine",
                    "embedding_model": current_model,
                }
            )
            _collection = None  # force re-fetch on next access
        elif not stored_model:
            collection.modify(metadata={
                "hnsw:space": "cosine",
                "embedding_model": current_model,
            })
    except Exception as e:
        logger.error(f"Model change check failed: {e}")


# Run at module load time to guard against stale vectors
reset_collection_if_model_changed()


def _get_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embed_model


def _embed(text: str) -> list[float]:
    return _get_model().encode(text, convert_to_numpy=True).tolist()


def check_cache(query: str) -> dict | None:
    """Return cached answer if a sufficiently similar, non-expired entry exists."""
    try:
        collection = _get_collection()
        embedding = _embed(query)

        results = collection.query(
            query_embeddings=[embedding],
            n_results=1,
            include=["documents", "metadatas", "distances"],
        )

        ids = results.get("ids", [[]])
        if not ids or not ids[0]:
            return None

        # ChromaDB cosine space: distance = 1 - cosine_similarity (range 0–2)
        distance = results["distances"][0][0]
        similarity = 1.0 - distance  # maps to [-1, 1]; 1 = identical

        if similarity < SIMILARITY_THRESHOLD:
            return None

        metadata = results["metadatas"][0][0]
        stored_at = float(metadata.get("stored_at", 0))
        source_type = metadata.get("source_type", "general")
        ttl = TTL_MAP.get(source_type, TTL_GUIDELINES)

        if time.time() - stored_at > ttl:
            collection.delete(ids=[results["ids"][0][0]])
            return None

        return {
            "answer": results["documents"][0][0],
            "similarity": round(similarity, 4),
            "source_type": source_type,
            "stored_at": stored_at,
            "cached": True,
        }
    except Exception:
        return None


def store_result(query: str, answer: str, source_type: str = "general") -> None:
    """Embed the query and store the answer with TTL metadata."""
    try:
        collection = _get_collection()
        embedding = _embed(query)
        doc_id = f"doc_{abs(hash(query))}_{int(time.time())}"

        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[answer],
            metadatas=[{
                "query": query[:500],
                "source_type": source_type,
                "stored_at": time.time(),
            }],
        )
    except Exception:
        pass


def get_cache_stats() -> dict:
    """Return basic stats about the ChromaDB collection."""
    try:
        collection = _get_collection()
        count = collection.count()
        return {
            "total_entries": count,
            "collection": CHROMA_COLLECTION,
            "embedding_model": EMBEDDING_MODEL,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "ttl_settings": {
                "guidelines_days": TTL_GUIDELINES // 86400,
                "drug_alerts_days": TTL_DRUG_ALERTS // 86400,
                "papers_days": TTL_PAPERS // 86400,
            },
        }
    except Exception as e:
        return {"total_entries": 0, "error": str(e)}
