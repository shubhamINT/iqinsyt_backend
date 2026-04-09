import logging
from typing import Any

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
MAX_RESULTS_PER_QUERY = 5
BRAVE_TIMEOUT_SECONDS = 6.0


async def brave_search(
    client: httpx.AsyncClient,
    query: str,
    count: int = MAX_RESULTS_PER_QUERY,
    request_id: str = "",
) -> list[dict[str, Any]]:
    """Single Brave Search query. Retained for future provider switching."""
    try:
        response = await client.get(
            BRAVE_SEARCH_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": settings.BRAVE_API_KEY,
            },
            params={"q": query, "count": count, "safesearch": "moderate"},
            timeout=BRAVE_TIMEOUT_SECONDS,
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
