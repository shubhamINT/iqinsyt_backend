import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from beanie import Document
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING

from src.core.config import settings


# ── Documents ─────────────────────────────────────────────────────────────────

class ResearchCache(Document):
    """4-hour TTL cache. Keyed by sha256(title)[:16] + ':' + YYYY-MM-DD."""
    cache_key: str
    event_title: str
    request_id: str
    sections: dict[str, Any]
    data_retrieval_available: bool
    generated_at: datetime
    expires_at: datetime

    class Settings:
        name = "research_cache"
        indexes = [
            IndexModel([("cache_key", ASCENDING)], unique=True),
            # MongoDB TTL index: removes doc when expires_at is in the past
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
        ]


class ResearchHistory(Document):
    """Permanent research history record. user_fingerprint = sha256(api_key)."""
    user_fingerprint: str
    event_title: str
    event_source: str
    request_id: str
    cached: bool
    data_retrieval_available: bool
    sections: dict[str, Any]
    generated_at: datetime
    created_at: datetime

    class Settings:
        name = "research_history"
        indexes = [
            IndexModel([("user_fingerprint", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("request_id", ASCENDING)], unique=True),
        ]


# ── Lifecycle ──────────────────────────────────────────────────────────────────

_mongo_client: Optional[AsyncIOMotorClient] = None


async def init_db() -> AsyncIOMotorClient:
    global _mongo_client
    from beanie import init_beanie

    _mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
    await init_beanie(
        database=_mongo_client[settings.MONGODB_DB_NAME],
        document_models=[ResearchCache, ResearchHistory],
    )
    return _mongo_client


async def close_db() -> None:
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_cache_key(event_title: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title_hash = hashlib.sha256(event_title.strip().lower().encode()).hexdigest()[:16]
    return f"{title_hash}:{date_str}"


def user_fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()
