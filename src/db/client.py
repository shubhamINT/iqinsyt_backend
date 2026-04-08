from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from src.core.config import settings
from src.db.models import ResearchCache, ResearchHistory

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
