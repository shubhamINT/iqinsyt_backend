from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from src.db.models import ResearchCache
from src.db.helpers import make_cache_key

CACHE_TTL_HOURS = 4


async def get_cached_research(event_title: str) -> Optional[ResearchCache]:
    """Returns a cache hit document, or None."""
    key = make_cache_key(event_title)
    return await ResearchCache.find_one(ResearchCache.cache_key == key)


async def set_cached_research(
    event_title: str,
    sections: dict[str, Any],
    request_id: str,
    data_retrieval_available: bool,
) -> ResearchCache:
    """Inserts (or replaces) the cache document for this event title today."""
    key = make_cache_key(event_title)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=CACHE_TTL_HOURS)

    # Remove any existing entry for the same key before inserting
    await ResearchCache.find(ResearchCache.cache_key == key).delete()

    doc = ResearchCache(
        cache_key=key,
        event_title=event_title,
        request_id=request_id,
        sections=sections,
        data_retrieval_available=data_retrieval_available,
        generated_at=now,
        expires_at=expires_at,
    )
    await doc.insert()
    return doc
