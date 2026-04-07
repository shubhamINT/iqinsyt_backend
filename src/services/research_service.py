import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from src.api.v1.schemas import ResearchRequest, ResearchSections
from src.db import ResearchHistory, user_fingerprint
from src.core.exceptions import IQinsytException
from src.services.cache_service import get_cached_research, set_cached_research
from src.services.llm_service import generate_sections
from src.services.search_service import gather_search_context

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


async def _emit_progress(
    progress_callback: ProgressCallback | None,
    stage: str,
    message: str,
    meta: dict[str, Any] | None = None,
) -> None:
    if progress_callback is None:
        return
    payload: dict[str, Any] = {"stage": stage, "message": message}
    if meta:
        payload["meta"] = meta
    await progress_callback(payload)


async def run_research_pipeline(
    body: ResearchRequest,
    api_key: str,
    request_id: str,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    fingerprint = user_fingerprint(api_key)

    # ── Step 1: Cache lookup ────────────────────────────────────────────────
    await _emit_progress(
        progress_callback,
        stage="cache.lookup.started",
        message="Checking cache for existing research",
    )
    cached = await get_cached_research(body.eventTitle)
    if cached:
        logger.info("Cache HIT for %r (request_id=%s)", body.eventTitle, request_id)
        await _emit_progress(
            progress_callback,
            stage="cache.lookup.hit",
            message="Cache hit; preparing cached response",
        )
        sections = ResearchSections(**cached.sections).model_dump()

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
        await _emit_progress(
            progress_callback,
            stage="history.write.scheduled",
            message="Scheduled cached history write",
        )

        return {
            "cached": True,
            "cachedAt": cached.generated_at.isoformat(),
            "sections": sections,
            "dataRetrievalAvailable": cached.data_retrieval_available,
            "generatedAt": cached.generated_at.isoformat(),
        }
    await _emit_progress(
        progress_callback,
        stage="cache.lookup.miss",
        message="Cache miss; running fresh pipeline",
    )

    # ── Step 2: Web search ──────────────────────────────────────────────────
    logger.info(
        "Cache MISS for %r — running pipeline (request_id=%s)",
        body.eventTitle,
        request_id,
    )
    await _emit_progress(
        progress_callback,
        stage="search.started",
        message="Gathering external web context",
    )
    context_text, data_retrieval_available = await gather_search_context(
        body.eventTitle, request_id
    )
    await _emit_progress(
        progress_callback,
        stage="search.completed",
        message=(
            "Web context retrieved"
            if data_retrieval_available
            else "No web context retrieved; continuing without external data"
        ),
        meta={"data_retrieval_available": data_retrieval_available},
    )

    # ── Step 3: LLM generation ───────────────────────────────────────────────
    await _emit_progress(
        progress_callback,
        stage="llm.started",
        message="Generating structured research response",
    )
    sections_dict = await generate_sections(
        event_title=body.eventTitle,
        event_source=body.eventSource,
        research_context=context_text,
        request_id=request_id,
    )
    if sections_dict is None:
        await _emit_progress(
            progress_callback,
            stage="llm.unavailable",
            message="LLM generation failed",
        )
        raise IQinsytException(
            status_code=503,
            error="LLM_UNAVAILABLE",
            message="Research temporarily unavailable. Please try again.",
            request_id=request_id,
        )
    await _emit_progress(
        progress_callback,
        stage="llm.completed",
        message="Research generated successfully",
    )

    generated_at = datetime.now(timezone.utc)

    # ── Step 4: Persist cache + history (parallel) ──────────────────────────
    await _emit_progress(
        progress_callback,
        stage="persist.started",
        message="Persisting cache and history",
    )
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
    await _emit_progress(
        progress_callback,
        stage="persist.completed",
        message="Persistence completed",
    )

    # ── Step 5: Return ───────────────────────────────────────────────────────
    return {
        "cached": False,
        "cachedAt": None,
        "sections": ResearchSections(**sections_dict).model_dump(),
        "dataRetrievalAvailable": data_retrieval_available,
        "generatedAt": generated_at.isoformat(),
    }


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
