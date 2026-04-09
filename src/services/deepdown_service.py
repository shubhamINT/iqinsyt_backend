from typing import Awaitable, Callable

from src.core.logging_config import get_logger
from src.services.llm.openai import TextDeltaCallback, call_llm_text
from src.services.llm.prompts import build_deepdown_prompt

logger = get_logger("services.deepdown")

TextCallback = Callable[[str], Awaitable[None]]


async def run_deepdown_pipeline(
    section_title: str,
    section_content: str,
    request_id: str = "",
    text_callback: TextDeltaCallback | None = None,
) -> str | None:
    """Deep-dive into a single research section using OpenAI web search.

    Streams text deltas via text_callback and returns the full result, or None on failure.
    """
    logger.info(
        "DeepDown pipeline started: section=%r, request_id=%s",
        section_title,
        request_id,
    )

    messages = build_deepdown_prompt(section_title, section_content)
    result = await call_llm_text(
        messages,
        request_id=request_id,
        text_callback=text_callback,
    )

    if result is None:
        logger.warning(
            "DeepDown pipeline produced no result: section=%r, request_id=%s",
            section_title,
            request_id,
        )
    else:
        logger.info(
            "DeepDown pipeline completed: section=%r, chars=%d, request_id=%s",
            section_title,
            len(result),
            request_id,
        )

    return result
