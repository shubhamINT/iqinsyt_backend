import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.api.v1.schemas import APIResponse, DeepDownRequest, ResearchRequest
from src.core.exceptions import IQinsytException
from src.core.logging_config import get_logger

logger = get_logger("api.research")

router = APIRouter(tags=["research"])


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _error_payload(
    request_id: str,
    error: str,
    message: str,
    status_code: int,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "message": message,
        "status_code": status_code,
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Endpoint ───────────────────────────────────────────────────────────────────


@router.post("/research")
async def create_research(
    body: ResearchRequest,
    request: Request,
    # api_key: str = Depends(get_api_key),
) -> StreamingResponse:
    from src.services.research_service import run_research_pipeline

    request_id = request.state.request_id
    logger.info(
        "Research request received: title=%r, source=%s, request_id=%s",
        body.eventTitle,
        body.eventSource,
        request_id,
    )

    async def event_stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        async def progress_callback(payload: dict[str, Any]) -> None:
            await queue.put(("progress", payload))

        async def section_callback(payload: dict[str, Any]) -> None:
            await queue.put(("section_delta", payload))

        async def worker() -> None:
            try:
                api_key = "123"  # Hard coded for now
                result = await run_research_pipeline(
                    body,
                    api_key,
                    request_id,
                    progress_callback=progress_callback,
                    section_callback=section_callback,
                )
                await queue.put(("result", result))
            except Exception as exc:
                await queue.put(("error", exc))

        worker_task = asyncio.create_task(worker())

        try:
            yield _sse_event(
                "research.started",
                {
                    "request_id": request_id,
                    "stage": "request.accepted",
                    "message": "Research request accepted",
                },
            )

            while True:
                event_type, payload = await queue.get()

                if event_type == "progress":
                    progress_data = {"request_id": request_id, **payload}
                    yield _sse_event("research.progress", progress_data)
                    continue

                if event_type == "section_delta":
                    delta_data = {"request_id": request_id, **payload}
                    yield _sse_event("research.section_delta", delta_data)
                    continue

                if event_type == "result":
                    logger.info(
                        "Research response sent: cached=%s, request_id=%s",
                        payload["cached"],
                        request_id,
                    )
                    final_payload = APIResponse(
                        success=True,
                        data=payload,
                        request_id=request_id,
                    ).model_dump()
                    yield _sse_event("research.completed", final_payload)
                    break

                if event_type == "error":
                    exc = payload
                    if isinstance(exc, IQinsytException):
                        logger.warning(
                            "Research pipeline business error: title=%r, request_id=%s, error=%s",
                            body.eventTitle,
                            request_id,
                            exc.error,
                        )
                        error_payload = _error_payload(
                            request_id=request_id,
                            error=exc.error,
                            message=exc.message,
                            status_code=exc.status_code,
                        )
                    else:
                        logger.error(
                            "Research pipeline failed: title=%r, request_id=%s, error_type=%s",
                            body.eventTitle,
                            request_id,
                            type(exc).__name__,
                        )
                        error_payload = _error_payload(
                            request_id=request_id,
                            error="INTERNAL_ERROR",
                            message="An unexpected error occurred.",
                            status_code=500,
                        )

                    yield _sse_event("research.error", error_payload)
                    break

        finally:
            if not worker_task.done():
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/research/deepdown")
async def deep_down(
    body: DeepDownRequest,
    request: Request,
) -> StreamingResponse:
    from src.services.deepdown_service import run_deepdown_pipeline

    request_id = request.state.request_id
    logger.info(
        "DeepDown request received: section=%r, request_id=%s",
        body.sectionTitle,
        request_id,
    )

    async def event_stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        async def text_callback(delta: str) -> None:
            await queue.put(("delta", delta))

        async def worker() -> None:
            try:
                result = await run_deepdown_pipeline(
                    body.sectionTitle,
                    body.sectionContent,
                    request_id=request_id,
                    text_callback=text_callback,
                )
                await queue.put(("result", result))
            except Exception as exc:
                await queue.put(("error", exc))

        worker_task = asyncio.create_task(worker())

        try:
            yield _sse_event(
                "deepdown.started",
                {"request_id": request_id, "section": body.sectionTitle},
            )

            accumulated: list[str] = []

            while True:
                event_type, payload = await queue.get()

                if event_type == "delta":
                    accumulated.append(payload)
                    yield _sse_event("deepdown.delta", {"delta": payload})
                    continue

                if event_type == "result":
                    full_text = payload or "".join(accumulated)
                    logger.info(
                        "DeepDown response sent: section=%r, request_id=%s",
                        body.sectionTitle,
                        request_id,
                    )
                    yield _sse_event(
                        "deepdown.completed",
                        {"request_id": request_id, "result": full_text},
                    )
                    break

                if event_type == "error":
                    exc = payload
                    if isinstance(exc, IQinsytException):
                        logger.warning(
                            "DeepDown pipeline error: section=%r, request_id=%s, error=%s",
                            body.sectionTitle,
                            request_id,
                            exc.error,
                        )
                        error_payload = _error_payload(
                            request_id=request_id,
                            error=exc.error,
                            message=exc.message,
                            status_code=exc.status_code,
                        )
                    else:
                        logger.error(
                            "DeepDown pipeline failed: section=%r, request_id=%s, error_type=%s",
                            body.sectionTitle,
                            request_id,
                            type(exc).__name__,
                        )
                        error_payload = _error_payload(
                            request_id=request_id,
                            error="INTERNAL_ERROR",
                            message="An unexpected error occurred.",
                            status_code=500,
                        )
                    yield _sse_event("deepdown.error", error_payload)
                    break

        finally:
            if not worker_task.done():
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
