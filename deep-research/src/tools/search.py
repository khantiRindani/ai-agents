"""
Cartographer — Search Tool (Tavily)
Abstracted search interface. All Explorer node calls go through here.
Swap search provider by replacing the implementation below — interface stays the same.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tavily import AsyncTavilyClient

from src.state import SearchResult


def _build_client() -> AsyncTavilyClient:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise EnvironmentError("TAVILY_API_KEY is not set. Add it to your .env file.")
    return AsyncTavilyClient(api_key=api_key)


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _search_one(client: AsyncTavilyClient, query: str, max_results: int) -> list[SearchResult]:
    """Single query search with retry. Returns empty list on final failure."""
    try:
        response = await client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_raw_content=False,
        )
        results: list[SearchResult] = []
        for r in response.get("results", []):
            results.append(
                SearchResult(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    content=r.get("content", ""),
                    score=float(r.get("score", 0.0)),
                    published_date=r.get("published_date", ""),
                )
            )
        return results
    except Exception as exc:
        # Log and re-raise for tenacity to handle
        print(f"[Search] Warning: query failed — {query!r}: {exc}")
        raise


async def parallel_search(
    queries: list[str],
    max_results_per_query: int | None = None,
) -> list[SearchResult]:
    """
    Run multiple Tavily searches in parallel (asyncio.gather).
    Deduplicates results by URL. Failed individual queries return empty lists.

    Args:
        queries: List of search queries (waypoints or uncharted zones)
        max_results_per_query: Overrides TAVILY_MAX_RESULTS env var

    Returns:
        Flat, deduplicated list of SearchResult
    """
    max_results = max_results_per_query or int(os.getenv("TAVILY_MAX_RESULTS", "5"))
    client = _build_client()

    tasks = [_search_one(client, q, max_results) for q in queries]
    results_nested: list[list[SearchResult]] = await asyncio.gather(
        *tasks, return_exceptions=False
    )

    # Flatten + deduplicate by URL
    seen_urls: set[str] = set()
    flat: list[SearchResult] = []
    for batch in results_nested:
        for result in batch:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                flat.append(result)

    # Sort by Tavily relevance score descending
    flat.sort(key=lambda r: r["score"], reverse=True)
    return flat
