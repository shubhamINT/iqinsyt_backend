import logging

import httpx

logger = logging.getLogger(__name__)

MAX_RESULTS_PER_QUERY = 5
SEARXNG_TIMEOUT_SECONDS = 6.0


async def searxng_search(
    client: httpx.AsyncClient,
    query: str,
    base_url: str,
    count: int = MAX_RESULTS_PER_QUERY,
    request_id: str = "",
) -> list[dict[str, str]]:
    """Single SearXNG query. Returns normalized result dicts."""
    q = query.strip()
    if not q:
        return []

    try:
        response = await client.get(
            f"{base_url}/search",
            params={"q": q, "format": "json"},
            timeout=SEARXNG_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning(
            "SearXNG query failed: query=%r, error=%s (request_id=%s)",
            q,
            type(exc).__name__,
            request_id,
        )
        return []

    normalized: list[dict[str, str]] = []
    for item in data.get("results", [])[:count]:
        normalized.append(
            {
                "title": (item.get("title") or "").strip(),
                "url": (item.get("url") or "").strip(),
                "description": (
                    item.get("content") or item.get("description") or ""
                ).strip(),
                "engine": (item.get("engine") or "").strip(),
            }
        )

    return normalized
