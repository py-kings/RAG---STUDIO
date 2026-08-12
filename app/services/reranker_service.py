"""
Reranker service.

Uses a CrossEncoder to rerank the candidate chunks returned
by the hybrid retriever.
"""

import logging

from flask import current_app
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

_reranker = None


def _get_reranker():
    """Load the reranker once and reuse it."""
    global _reranker

    if _reranker is None:
        model_name = current_app.config.get(
            "RERANKER_MODEL_NAME",
            "BAAI/bge-reranker-base",
        )

        logger.info(
            "Loading reranker model %s",
            model_name,
        )

        _reranker = CrossEncoder(
            model_name,
            max_length=512,
        )

    return _reranker


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Rerank retrieved chunks based on query-document relevance.

    Args:
        query: User's question.
        candidates: Results returned by hybrid retrieval.
        top_k: Number of final chunks to keep.

    Returns:
        Reranked chunks.
    """

    if not candidates:
        return []

    model = _get_reranker()

    pairs = [
        (query, candidate["text"])
        for candidate in candidates
    ]

    scores = model.predict(pairs)

    reranked = []

    for candidate, score in zip(candidates, scores):
        result = candidate.copy()
        result["rerank_score"] = float(score)
        reranked.append(result)

    reranked.sort(
        key=lambda x: x["rerank_score"],
        reverse=True,
    )

    return reranked[:top_k]
