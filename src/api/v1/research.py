from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.core.dependencies import get_api_key
from src.core.logging_config import get_logger

logger = get_logger("api.research")

router = APIRouter(tags=["research"])


# ── Schemas ────────────────────────────────────────────────────────────────────


class ResearchRequest(BaseModel):
    eventTitle: str = Field(min_length=1, max_length=500)
    eventSource: str = Field(min_length=1, max_length=253)
    timestamp: int = Field(description="Unix milliseconds from the extension")


class ResearchSections(BaseModel):
    eventSummary: str
    keyVariables: str
    historicalContext: str
    currentDrivers: str
    riskFactors: str
    dataConfidence: str
    dataGaps: str


class ResearchResponse(BaseModel):
    requestId: str
    cached: bool
    cachedAt: Optional[str]
    sections: ResearchSections
    dataRetrievalAvailable: bool
    generatedAt: str


# ── Endpoint ───────────────────────────────────────────────────────────────────


@router.post("/research", response_model=ResearchResponse)
async def create_research(
    body: ResearchRequest,
    request: Request,
    api_key: str = Depends(get_api_key),
) -> ResearchResponse:
    from src.services.research_service import run_research_pipeline

    request_id = request.state.request_id
    logger.info(
        "Research request received: title=%r, source=%s, request_id=%s",
        body.eventTitle,
        body.eventSource,
        request_id,
    )

    try:
        result = await run_research_pipeline(body, api_key, request_id)
        logger.info(
            "Research response sent: cached=%s, request_id=%s",
            result.cached,
            request_id,
        )
        return result
    except Exception as exc:
        logger.error(
            "Research pipeline failed: title=%r, request_id=%s, error_type=%s",
            body.eventTitle,
            request_id,
            type(exc).__name__,
        )
        raise
