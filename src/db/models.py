from datetime import datetime
from typing import Any

from beanie import Document
from pymongo import ASCENDING, DESCENDING, IndexModel


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
