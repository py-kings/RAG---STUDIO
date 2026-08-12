"""
Hybrid Retrieval Service.

Combines:
1. Semantic/vector search using ChromaDB
2. Keyword search using BM25
3. Reciprocal Rank Fusion (RRF)
"""

import re
import logging

from app.services import embedding_service

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer for BM25."""
    return re.findall(r"\b\w+\b", text.lower())


def _bm25_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Perform BM25 keyword search over indexed ChromaDB chunks.
    """

    from rank_bm25 import BM25Okapi

    collection = embedding_service.get_collection()

    data = collection.get(
        include=["documents", "metadatas"]
    )

    documents = data.get("documents") or []
    metadatas = data.get("metadatas") or []

    if not documents:
        logger.warning("No documents found in ChromaDB for BM25 search")
        return []

    tokenized_documents = [
        _tokenize(document)
        for document in documents
    ]

    query_tokens = _tokenize(query)

    if not query_tokens:
        return []

    bm25 = BM25Okapi(tokenized_documents)

    scores = bm25.get_scores(query_tokens)

    ranked_indexes = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True
    )[:top_k]

    results = []

    for index in ranked_indexes:
        results.append({
            "text": documents[index],
            "metadata": metadatas[index],
            "bm25_score": float(scores[index]),
        })

    return results


def _rrf_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """
    Combine vector and BM25 rankings using
    Reciprocal Rank Fusion.

    RRF score = 1 / (k + rank)
    """

    fused = {}

    # -------------------------
    # Vector results
    # -------------------------

    for rank, result in enumerate(vector_results, start=1):

        metadata = result["metadata"]

        key = (
            metadata.get("document_id"),
            metadata.get("chunk_index"),
        )

        if key not in fused:
            fused[key] = {
                "text": result["text"],
                "metadata": metadata,
                "rrf_score": 0.0,
                "sources": [],
            }

        fused[key]["rrf_score"] += 1 / (k + rank)

        if "vector" not in fused[key]["sources"]:
            fused[key]["sources"].append("vector")

    # -------------------------
    # BM25 results
    # -------------------------

    for rank, result in enumerate(bm25_results, start=1):

        metadata = result["metadata"]

        key = (
            metadata.get("document_id"),
            metadata.get("chunk_index"),
        )

        if key not in fused:
            fused[key] = {
                "text": result["text"],
                "metadata": metadata,
                "rrf_score": 0.0,
                "sources": [],
            }

        fused[key]["rrf_score"] += 1 / (k + rank)

        if "bm25" not in fused[key]["sources"]:
            fused[key]["sources"].append("bm25")

    # -------------------------
    # Final ranking
    # -------------------------

    ranked = sorted(
        fused.values(),
        key=lambda x: x["rrf_score"],
        reverse=True
    )

    return ranked[:top_k]


def hybrid_search(
    query: str,
    top_k: int = 5,
    candidate_k: int = 10,
) -> list[dict]:
    """
    Run:

    Query
      ↓
    Vector Search + BM25
      ↓
    RRF
      ↓
    Top-K results
    """

    logger.info("Starting hybrid search: %r", query)

    # Semantic/vector search
    vector_results = embedding_service.search_similar_chunks(
        query,
        top_k=candidate_k,
    )

    # Keyword search
    bm25_results = _bm25_search(
        query,
        top_k=candidate_k,
    )

    logger.info(
        "Retrieved %d vector results and %d BM25 results",
        len(vector_results),
        len(bm25_results),
    )

    # Combine rankings
    results = _rrf_fusion(
        vector_results,
        bm25_results,
        top_k=top_k,
    )

    # Debug information
    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"]

        logger.info(
            "RRF #%d | sources=%s | score=%.5f | document=%s | chunk=%s",
            rank,
            result["sources"],
            result["rrf_score"],
            metadata.get("document_id"),
            metadata.get("chunk_index"),
        )

    return results