"""
Query Router Service.

Determines which knowledge source should be used for a query.

Routes:
DOCUMENT -> internal uploaded documents
WEB      -> external/current information
BOTH     -> internal documents + external information
"""

import logging
import re

logger = logging.getLogger(__name__)


# ============================================================
# WEB / EXTERNAL INFORMATION
# ============================================================

WEB_PATTERNS = [
    # Current / freshness
    r"\blatest\b",
    r"\btoday\b",
    r"\bcurrent\b",
    r"\bcurrently\b",
    r"\brecent\b",
    r"\brecently\b",
    r"\b2026\b",
    r"\bnews\b",
    r"\btrending\b",
    r"\btoday's\b",
    r"\btodays\b",
    r"\bthis year\b",
    r"\bthis month\b",
    r"\bthis week\b",
    r"\bwhat is happening\b",
    r"\bwhat's happening\b",
    r"\baccording to recent\b",
    r"\bcurrent trends?\b",

    # Market / industry
    r"\bmarket trends?\b",
    r"\bindustry trends?\b",
    r"\bjob market\b",
    r"\bjob openings\b",
    r"\bjob requirements\b",
    r"\bjob demand\b",
    r"\bindustry requirements\b",

    # General external research
    r"\bsearch the web\b",
    r"\bsearch online\b",
    r"\bonline sources?\b",
    r"\bweb sources?\b",
    r"\bexternal sources?\b",
    r"\baccording to the internet\b",

    # Comparisons / research
    r"\bwhat are the limitations\b",
    r"\badvantages and disadvantages\b",
    r"\bpros and cons\b",
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bbenchmark\b",
    r"\bindustry standard\b",
    r"\bindustry standards\b",
    r"\bbest practices\b",
]


# ============================================================
# DOCUMENT / INTERNAL KNOWLEDGE
# ============================================================

DOCUMENT_PATTERNS = [
    # Resume / CV
    r"\bmy resume\b",
    r"\bmy cv\b",
    r"\bresume\b",
    r"\bcv\b",

    # Uploaded files
    r"\buploaded document\b",
    r"\buploaded file\b",
    r"\buploaded pdf\b",
    r"\bthe document\b",
    r"\bthis document\b",
    r"\bmy document\b",
    r"\bthe pdf\b",
    r"\bthis pdf\b",
    r"\bin the pdf\b",
    r"\bin this pdf\b",
    r"\bin my pdf\b",
    r"\baccording to the document\b",
    r"\baccording to my document\b",
    r"\baccording to the pdf\b",
    r"\bfrom my document\b",
    r"\bfrom my resume\b",

    # Explicit internal knowledge
    r"\bin the uploaded\b",
    r"\bfrom the uploaded\b",
    r"\bmentioned in the document\b",
    r"\bmentioned in my resume\b",
    r"\bmentioned in the pdf\b",
    r"\baccording to my files?\b",
]


# ============================================================
# BOTH / HYBRID QUESTIONS
#
# These questions need:
#   1. Internal user/document information
#   2. External/current information
#
# Example:
# "What skills am I missing for current Data Analyst jobs?"
#
# We need the resume + current job market.
# ============================================================

BOTH_PATTERNS = [
    # Resume + current market
    r"\bskills am i missing\b",
    r"\bwhat skills am i missing\b",
    r"\bwhat skills do i need\b",
    r"\bskills i need\b",
    r"\bskills required for\b",
    r"\bskills needed for\b",

    # Resume comparison
    r"\bcompare my resume\b",
    r"\bcompare my cv\b",
    r"\bcompare my skills\b",
    r"\bcompare my experience\b",

    r"\bresume.*current\b",
    r"\bresume.*market\b",
    r"\bresume.*job\b",
    r"\bcv.*current\b",
    r"\bcv.*market\b",
    r"\bcv.*job\b",

    # User profile vs industry
    r"\bhow do i compare\b",
    r"\bhow do my skills compare\b",
    r"\bhow does my resume compare\b",
    r"\bwhat am i missing\b",
    r"\bwhat should i learn\b",
    r"\bwhat should i improve\b",
    r"\bwhat should i add to my resume\b",

    # Current job requirements + personal profile
    r"\bmy skills.*data analyst\b",
    r"\bmy resume.*data analyst\b",
    r"\bmy cv.*data analyst\b",
]


# ============================================================
# HELPER
# ============================================================

def _matches_any(query: str, patterns: list[str]) -> bool:
    """
    Return True if the query matches any supplied pattern.
    """

    return any(
        re.search(pattern, query, re.IGNORECASE)
        for pattern in patterns
    )


# ============================================================
# ROUTER
# ============================================================

def route_query(query: str) -> str:
    """
    Determine the appropriate retrieval source.

    Returns:
        DOCUMENT
        WEB
        BOTH
    """

    query = query.strip()

    if not query:
        return "DOCUMENT"

    # --------------------------------------------------------
    # Check all three intents
    # --------------------------------------------------------

    document_query = _matches_any(
        query,
        DOCUMENT_PATTERNS,
    )

    web_query = _matches_any(
        query,
        WEB_PATTERNS,
    )

    both_query = _matches_any(
        query,
        BOTH_PATTERNS,
    )

    # --------------------------------------------------------
    # BOTH has highest priority
    #
    # Example:
    # "What skills am I missing for current Data Analyst jobs?"
    #
    # Needs:
    # Resume -> internal RAG
    # Job market -> Tavily
    # --------------------------------------------------------

    if both_query:
        route = "BOTH"

    # --------------------------------------------------------
    # Explicit document question
    # --------------------------------------------------------

    elif document_query and not web_query:
        route = "DOCUMENT"

    # --------------------------------------------------------
    # Explicit web/current question
    # --------------------------------------------------------

    elif web_query and not document_query:
        route = "WEB"

    # --------------------------------------------------------
    # If both signals appear naturally
    # --------------------------------------------------------

    elif document_query and web_query:
        route = "BOTH"

    # --------------------------------------------------------
    # Default
    #
    # General knowledge / conceptual questions are better
    # handled through the web rather than pretending that the
    # uploaded documents contain the answer.
    # --------------------------------------------------------

    else:
        route = "WEB"

    logger.info(
        "Query route: %s | question=%r",
        route,
        query,
    )

    return route