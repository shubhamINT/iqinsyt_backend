import asyncio
import logging

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
MAX_RESULTS_PER_QUERY = 5
MAX_CONTEXT_RESULTS = 6
MAX_CONTEXT_CHARS = 9000  # ~2,250 tokens, well within LLM window


async def brave_search(
    client: httpx.AsyncClient,
    query: str,
    count: int = MAX_RESULTS_PER_QUERY,
    request_id: str = "",
) -> list[dict]:
    """Single Brave Search query. Returns list of result dicts."""
    try:
        response = await client.get(
            BRAVE_SEARCH_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": settings.BRAVE_API_KEY,
            },
            params={"q": query, "count": count, "safesearch": "moderate"},
            timeout=6.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("web", {}).get("results", [])
    except Exception as exc:
        logger.warning(
            "Brave Search query failed: query=%r, error=%s (request_id=%s)",
            query,
            type(exc).__name__,
            request_id,
        )
        return []


async def gather_search_context(
    event_title: str, request_id: str = ""
) -> tuple[str, bool]:
    """
    Runs 3 parallel Brave Search queries, deduplicates by URL, formats into
    a numbered context string for the LLM prompt.

    Returns (context_text, data_retrieval_available).
    Returns ("", False) on complete failure.
    """
    if not settings.BRAVE_API_KEY:
        logger.warning(
            "BRAVE_API_KEY not set — skipping web search (request_id=%s)", request_id
        )
        return "", False

    queries = [
        f"{event_title} news",
        f"{event_title} analysis",
        f"{event_title} preview",
    ]

    async with httpx.AsyncClient() as client:
        results_per_query = await asyncio.gather(
            *[brave_search(client, q, request_id=request_id) for q in queries]
        )

    # Deduplicate by URL, preserve order
    seen_urls: set[str] = set()
    unique_results: list[dict] = []
    for results in results_per_query:
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)
                if len(unique_results) >= MAX_CONTEXT_RESULTS:
                    break
        if len(unique_results) >= MAX_CONTEXT_RESULTS:
            break

    if not unique_results:
        return "", False

    lines: list[str] = []
    for i, r in enumerate(unique_results, start=1):
        title = r.get("title", "").strip()
        url = r.get("url", "").strip()
        description = r.get("description", "").strip()
        lines.append(f"[{i}] {title}\n{url}\n{description}")

    context_text = "\n\n".join(lines)

    # Cap context length to avoid token overflow
    if len(context_text) > MAX_CONTEXT_CHARS:
        context_text = context_text[:MAX_CONTEXT_CHARS]

    return context_text, True
