"""
RAG service.

Pipeline:

DOCUMENT:
Question
    ↓
Hybrid Search
(Vector Search + BM25 + RRF)
    ↓
Cross-Encoder Reranker
    ↓
Top Chunks
    ↓
Gemini
    ↓
Answer

WEB:
Question
    ↓
Tavily Web Search
    ↓
Web Context
    ↓
Gemini
    ↓
Answer

BOTH:
Question
    ↓
Query Router
    ↓
    ├── Internal Document RAG
    │       ↓
    │   Hybrid Search
    │       ↓
    │   Reranker
    │
    └── Web Search
            ↓
        Tavily
            ↓
    Combined Context
            ↓
          Gemini
            ↓
          Answer

Persists:
- ChatHistory
- QueryLog
"""

import time
import logging

from app import db
from app.models import ChatHistory, QueryLog, Document

from app.services import (
    embedding_service,
    llm_service,
    hybrid_search_service,
    reranker_service,
    query_router_service,
    web_search_service,
)

from app.services.llm_service import LLMError


logger = logging.getLogger(__name__)


TOP_K = 5


def _build_context(hits: list) -> str:
    """
    Build context from internal document chunks.

    Each chunk is labeled with its source document and page.
    """

    if not hits:
        return ""

    parts = []

    for hit in hits:

        meta = hit["metadata"]

        page = meta.get("page", -1)

        page_label = (
            f", page {page}"
            if page and page != -1
            else ""
        )

        parts.append(
            f"[Source: {meta.get('title', 'Unknown document')}"
            f"{page_label}]\n"
            f"{hit['text']}"
        )

    return "\n\n".join(parts)


def _build_web_context(results: list) -> str:
    """
    Build context from Tavily web search results.

    Each result contains:
    - title
    - URL
    - content
    """

    if not results:
        return ""

    parts = []

    for result in results:

        title = result.get(
            "title",
            "Unknown web source"
        )

        url = result.get(
            "url",
            ""
        )

        content = result.get(
            "content",
            ""
        )

        parts.append(
            f"[Web Source: {title}]\n"
            f"URL: {url}\n"
            f"{content}"
        )

    return "\n\n".join(parts)


def ask_question(user, question: str) -> dict:
    """
    Run the complete RAG pipeline for a user question.

    The query router determines whether the question requires:

    DOCUMENT
        Internal document retrieval.

    WEB
        External web search.

    BOTH
        Internal documents + external web search.
    """

    start = time.perf_counter()

    # =========================================================
    # STEP 1: QUERY ROUTING
    # =========================================================

    route = query_router_service.route_query(
        question
    )

    logger.info(
        "Question routed to: %s",
        route,
    )

    # =========================================================
    # STEP 2: RETRIEVAL
    # =========================================================

    try:

        # -----------------------------------------
        # Internal document retrieval
        # -----------------------------------------

        hits = []

        if route in ("DOCUMENT", "BOTH"):

            logger.info(
                "Running internal document retrieval"
            )

            # Hybrid retrieval:
            # Vector Search + BM25 + RRF
            candidates = (
                hybrid_search_service.hybrid_search(
                    question,
                    top_k=10,
                    candidate_k=10,
                )
            )

            # Cross-encoder reranking
            hits = reranker_service.rerank(
                question,
                candidates,
                top_k=TOP_K,
            )

            # Log final reranked results
            for rank, hit in enumerate(
                hits,
                start=1
            ):

                logger.info(
                    "RERANK #%d | score=%.5f | "
                    "document=%s | chunk=%s",

                    rank,

                    hit["rerank_score"],

                    hit["metadata"].get(
                        "document_id"
                    ),

                    hit["metadata"].get(
                        "chunk_index"
                    ),
                )

        # -----------------------------------------
        # External web retrieval
        # -----------------------------------------

        web_results = []

        if route in ("WEB", "BOTH"):

            logger.info(
                "Running external web search"
            )

            web_results = (
                web_search_service.search_web(
                    question,
                    max_results=5,
                )
            )

    except Exception as exc:
        logger.exception(
            "Retrieval failed for question: %r",
            question,
        )

        _log_query(
            user,
            question,
            success=False,
            start=start,
        )

        return {
            "error": f"Search failed: {exc}"
        }

    # =========================================================
    # STEP 3: BUILD CONTEXT
    # =========================================================

    document_context = _build_context(
        hits
    )

    web_context = _build_web_context(
        web_results
    )

    # =========================================================
    # STEP 4: COMBINE CONTEXT
    # =========================================================

    context_parts = []

    if document_context:

        context_parts.append(
            "INTERNAL DOCUMENT CONTEXT:\n"
            + document_context
        )

    if web_context:

        context_parts.append(
            "WEB SEARCH CONTEXT:\n"
            + web_context
        )

    combined_context = "\n\n".join(
        context_parts
    )

    # If no context was retrieved
    if not combined_context:

        combined_context = (
            "(No relevant information was retrieved.)"
        )

    logger.info(
        "Context prepared | route=%s | "
        "document_chunks=%d | web_results=%d",

        route,

        len(hits),

        len(web_results),
    )

    # =========================================================
    # STEP 5: GEMINI
    # =========================================================

    try:

        answer = llm_service.generate_answer(
            question,
            combined_context,
        )

    except LLMError as exc:

        _log_query(
            user,
            question,
            success=False,
            start=start,
        )

        return {
            "error": str(exc)
        }

    # =========================================================
    # STEP 6: RESPONSE TIME
    # =========================================================

    response_time_ms = int(
        (
            time.perf_counter()
            - start
        ) * 1000
    )

    # =========================================================
    # STEP 7: INTERNAL SOURCE CITATION
    # =========================================================

    top_hit = (
        hits[0]
        if hits
        else None
    )

    source_document = None
    source_page = None

    if top_hit:

        doc_id = (
            top_hit["metadata"]
            .get("document_id")
        )

        if doc_id:

            source_document = (
                db.session.get(
                    Document,
                    doc_id,
                )
            )

        page = (
            top_hit["metadata"]
            .get("page")
        )

        source_page = (
            page
            if page and page != -1
            else None
        )

    # =========================================================
    # STEP 8: PREPARE WEB CITATIONS
    # =========================================================

    web_sources = []

    for result in web_results:

        url = result.get("url")

        if not url:
            continue

        web_sources.append({
            "title": result.get(
                "title",
                "Web Source"
            ),
            "url": url,
            "score": result.get(
                "score",
                0.0
            ),
        })

    # Keep only the top 5 sources.
    web_sources = web_sources[:5]

    # =========================================================
    # STEP 9: SAVE CHAT HISTORY
    # =========================================================

    chat_entry = ChatHistory(
        user=user,
        question=question,
        response=answer,

        # Internal citation
        source_document=source_document,
        source_page=source_page,

        # External citations
        web_sources=web_sources or None,

        response_time_ms=response_time_ms,
    )

    db.session.add(chat_entry)
    # =========================================================
    # STEP 9: LOG QUERY
    # =========================================================

    _log_query(
        user,
        question,
        success=True,
        start=start,
        response_time_ms=response_time_ms,
    )

    # =========================================================
    # STEP 10: RETURN RESULT
    # =========================================================

    return {
        "answer": answer,
        "source_document": source_document,
        "source_page": source_page,
        "chunks_used": len(hits),
        "route": route,
        "web_results": len(web_results),
    }


def _log_query(
    user,
    question: str,
    success: bool,
    start: float,
    response_time_ms: int = None,
) -> None:
    """
    Persist query analytics.
    """

    if response_time_ms is None:

        response_time_ms = int(
            (
                time.perf_counter()
                - start
            ) * 1000
        )

    db.session.add(
        QueryLog(
            user=user,
            department=user.department,
            query_text=question,
            success=success,
            response_time_ms=response_time_ms,
        )
    )

    db.session.commit()