import secrets

from fastapi import Header, HTTPException, status

from src.core.config import settings


async def get_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    if not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_API_KEY", "message": "Invalid or missing API key."},
        )
    return x_api_key
