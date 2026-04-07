from fastapi import APIRouter, Depends, Request

from src.api.v1.schemas import APIResponse, ResearchRequest, ResearchResponse
from src.core.dependencies import get_api_key
from src.core.logging_config import get_logger

logger = get_logger("api.research")

router = APIRouter(tags=["research"])





# ── Endpoint ───────────────────────────────────────────────────────────────────


@router.post("/research", response_model=APIResponse[ResearchResponse])
async def create_research(
    body: ResearchRequest,
    request: Request,
    api_key: str = Depends(get_api_key),
) -> APIResponse[ResearchResponse]:
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
        return APIResponse(success=True, data=result, request_id=request_id)
    except Exception as exc:
        logger.error(
            "Research pipeline failed: title=%r, request_id=%s, error_type=%s",
            body.eventTitle,
            request_id,
            type(exc).__name__,
        )
        raise
