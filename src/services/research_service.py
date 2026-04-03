import asyncio
import logging
from datetime import datetime, timezone

from src.api.v1.research import ResearchRequest, ResearchResponse, ResearchSections
from src.core.database import ResearchHistory, user_fingerprint
from src.core.exceptions import IQinsytException
from src.services.cache_service import get_cached_research, set_cached_research
from src.services.compliance_service import run_compliant_pipeline
from src.services.search_service import gather_search_context

logger = logging.getLogger(__name__)


async def run_research_pipeline(
    body: ResearchRequest,
    api_key: str,
    request_id: str,
) -> ResearchResponse:
    fingerprint = user_fingerprint(api_key)

    # ── Step 1: Cache lookup ────────────────────────────────────────────────
    cached = await get_cached_research(body.eventTitle)
    if cached:
        logger.info("Cache HIT for %r (request_id=%s)", body.eventTitle, request_id)
        sections = ResearchSections(**cached.sections)

        # Fire-and-forget history write (don't await — don't block response)
        asyncio.create_task(
            _write_history(
                fingerprint=fingerprint,
                body=body,
                request_id=request_id,
                cached=True,
                sections=cached.sections,
                data_retrieval_available=cached.data_retrieval_available,
                generated_at=cached.generated_at,
            )
        )

        return ResearchResponse(
            requestId=request_id,
            cached=True,
            cachedAt=cached.generated_at.isoformat(),
            sections=sections,
            dataRetrievalAvailable=cached.data_retrieval_available,
            generatedAt=cached.generated_at.isoformat(),
        )

    # ── Step 2: Web search ──────────────────────────────────────────────────
    logger.info(
        "Cache MISS for %r — running pipeline (request_id=%s)",
        body.eventTitle,
        request_id,
    )
    context_text, data_retrieval_available = await gather_search_context(
        body.eventTitle, request_id
    )

    # ── Step 3+4: Compliant LLM pipeline ────────────────────────────────────
    sections_dict, _ = await run_compliant_pipeline(
        event_title=body.eventTitle,
        event_source=body.eventSource,
        research_context=context_text,
        request_id=request_id,
    )

    # ── Step 5: Check for total LLM failure (all placeholders = no real data)
    from src.services.compliance_service import UNAVAILABLE_PLACEHOLDER

    if all(v == UNAVAILABLE_PLACEHOLDER for v in sections_dict.values()):
        raise IQinsytException(
            status_code=503,
            error="LLM_UNAVAILABLE",
            message="Research temporarily unavailable. Please try again.",
            request_id=request_id,
        )

    generated_at = datetime.now(timezone.utc)

    # ── Step 6: Persist cache + history (parallel) ──────────────────────────
    await asyncio.gather(
        set_cached_research(
            event_title=body.eventTitle,
            sections=sections_dict,
            request_id=request_id,
            data_retrieval_available=data_retrieval_available,
        ),
        _write_history(
            fingerprint=fingerprint,
            body=body,
            request_id=request_id,
            cached=False,
            sections=sections_dict,
            data_retrieval_available=data_retrieval_available,
            generated_at=generated_at,
        ),
    )

    # ── Step 7: Return ───────────────────────────────────────────────────────
    return ResearchResponse(
        requestId=request_id,
        cached=False,
        cachedAt=None,
        sections=ResearchSections(**sections_dict),
        dataRetrievalAvailable=data_retrieval_available,
        generatedAt=generated_at.isoformat(),
    )


async def _write_history(
    fingerprint: str,
    body: ResearchRequest,
    request_id: str,
    cached: bool,
    sections: dict,
    data_retrieval_available: bool,
    generated_at: datetime,
) -> None:
    try:
        doc = ResearchHistory(
            user_fingerprint=fingerprint,
            event_title=body.eventTitle,
            event_source=body.eventSource,
            request_id=request_id,
            cached=cached,
            data_retrieval_available=data_retrieval_available,
            sections=sections,
            generated_at=generated_at,
            created_at=datetime.now(timezone.utc),
        )
        await doc.insert()
    except Exception as exc:
        logger.warning("Failed to write history (request_id=%s): %s", request_id, exc)
