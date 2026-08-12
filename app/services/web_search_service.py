"""
Web Search Service.

Retrieves current/external information using Tavily.
"""

import logging

from flask import current_app
from tavily import TavilyClient

logger = logging.getLogger(__name__)


def search_web(
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """
    Search the web and return structured results.
    """

    api_key = current_app.config.get("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is not configured."
        )

    client = TavilyClient(api_key=api_key)

    logger.info(
        "Performing web search: %r",
        query,
    )

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
        include_answer=False,
    )

    results = []

    for result in response.get("results", []):
        results.append({
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content": result.get("content", ""),
            "score": result.get("score", 0.0),
        })

    logger.info(
        "Web search returned %d results",
        len(results),
    )

    return results