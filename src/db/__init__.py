import hashlib
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from src.core.config import settings
from src.db.models import ResearchCache, ResearchHistory


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
