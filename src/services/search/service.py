import asyncio
import logging

import httpx

from src.core.config import settings
from src.services.search.searxng import searxng_search

logger = logging.getLogger(__name__)

MAX_CONTEXT_RESULTS = 6
MAX_CONTEXT_CHARS = 9000  # ~2,250 tokens, well within LLM window


async def gather_search_context(
    event_title: str, request_id: str = ""
) -> tuple[str, bool]:
    """
    Runs 3 parallel SearXNG queries, deduplicates by URL, formats into
    a numbered context string for the LLM prompt.

    Returns (context_text, data_retrieval_available).
    Returns ("", False) on complete failure.
    """
    base_url = settings.SEARXNG_BASE_URL.strip().rstrip("/")
    if not base_url:
        logger.warning(
            "SEARXNG_BASE_URL not set — skipping web search (request_id=%s)",
            request_id,
        )
        return "", False

    queries = [
        f"{event_title} news",
        f"{event_title} analysis",
        f"{event_title} preview",
    ]

    async with httpx.AsyncClient() as client:
        results_per_query = await asyncio.gather(
            *[
                searxng_search(client, q, base_url=base_url, request_id=request_id)
                for q in queries
            ]
        )

    # Deduplicate by URL, preserve order
    seen_urls: set[str] = set()
    unique_results: list[dict[str, str]] = []
    for results in results_per_query:
        for result in results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
                if len(unique_results) >= MAX_CONTEXT_RESULTS:
                    break
        if len(unique_results) >= MAX_CONTEXT_RESULTS:
            break

    if not unique_results:
        return "", False

    lines: list[str] = []
    for index, result in enumerate(unique_results, start=1):
        title = result.get("title", "")
        url = result.get("url", "")
        description = result.get("description", "")
        lines.append(f"[{index}] {title}\n{url}\n{description}")

    context_text = "\n\n".join(lines)

    # Cap context length to avoid token overflow
    if len(context_text) > MAX_CONTEXT_CHARS:
        context_text = context_text[:MAX_CONTEXT_CHARS]

    return context_text, True
