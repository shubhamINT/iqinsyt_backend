import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from src.core.config import settings
from src.services.prompts import REQUIRED_KEYS, SECTION_INSTRUCTIONS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
LLM_TIMEOUT_SECONDS = 8.0


def assemble_prompt(
    event_title: str,
    event_source: str,
    research_context: str,
) -> list[dict[str, str]]:
    context_block = (
        research_context
        if research_context
        else "[No external data available — use only general knowledge.]"
    )
    user_content = (
        f"Event: {event_title}\n"
        f"Detected on: {event_source}\n\n"
        f"Research context:\n{context_block}\n\n"
        f"{SECTION_INSTRUCTIONS}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


async def generate_sections(
    event_title: str,
    event_source: str,
    research_context: str,
    request_id: str = "",
) -> dict[str, str] | None:
    """Assembles the prompt and calls the LLM. Returns sections dict or None on failure."""
    messages = assemble_prompt(event_title, event_source, research_context)
    client = _get_openai_client()
    return await call_llm(messages, client, request_id)


def _get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
        return "\n".join(p for p in parts if p)
    return str(content)


def _messages_to_responses_payload(
    messages: list[dict[str, Any]],
) -> tuple[str | None, Any]:
    instructions_parts: list[str] = []
    input_items: list[dict[str, str]] = []

    for message in messages:
        role = str(message.get("role", "user"))
        text = _message_content_to_text(message.get("content", ""))

        if role == "system":
            if text:
                instructions_parts.append(text)
            continue

        mapped_role = role if role in {"user", "assistant", "developer"} else "user"
        input_items.append({"role": mapped_role, "content": text})

    instructions = "\n\n".join(instructions_parts).strip() or None

    if len(input_items) == 1 and input_items[0]["role"] == "user":
        input_payload: Any = input_items[0]["content"]
    else:
        input_payload = input_items

    return instructions, input_payload


def _extract_text_from_final_response(response: Any) -> str:
    chunks: list[str] = []
    for output_item in getattr(response, "output", []) or []:
        if getattr(output_item, "type", "") != "message":
            continue
        for part in getattr(output_item, "content", []) or []:
            if getattr(part, "type", "") == "output_text":
                text_value = getattr(part, "text", "")
                if text_value:
                    chunks.append(str(text_value))
    return "".join(chunks).strip()


def _parse_json_payload(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(content[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


async def call_llm(
    messages: list[dict[str, Any]],
    client: AsyncOpenAI | None = None,
    request_id: str = "",
) -> dict[str, str] | None:
    """Returns parsed sections dict, or None on any failure."""
    if client is None:
        client = _get_openai_client()

    instructions, input_payload = _messages_to_responses_payload(messages)

    try:
        text_chunks: list[str] = []
        done_text = ""
        final_response: Any = None

        async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
            async with client.responses.stream(
                model=MODEL,
                input=input_payload,
                instructions=instructions,
                text={"format": {"type": "json_object"}},
                temperature=0.2,
                max_output_tokens=2000,
            ) as stream:
                async for event in stream:
                    if event.type == "response.output_text.delta":
                        text_chunks.append(event.delta)
                    elif event.type == "response.output_text.done":
                        done_text = event.text

                final_response = await stream.get_final_response()

        content = "".join(text_chunks).strip()
        if not content:
            content = done_text.strip()
        if not content and final_response is not None:
            content = _extract_text_from_final_response(final_response)

        if not content:
            logger.warning("LLM stream produced no content (request_id=%s)", request_id)
            return None

        parsed = _parse_json_payload(content)
        if not parsed:
            logger.warning(
                "LLM returned invalid JSON payload (request_id=%s)",
                request_id,
            )
            return None

        missing = REQUIRED_KEYS - parsed.keys()
        if missing:
            logger.warning(
                "LLM response missing required keys: %s (request_id=%s)",
                missing,
                request_id,
            )
            return None

        return {key: str(parsed[key]) for key in REQUIRED_KEYS}

    except TimeoutError:
        logger.warning("LLM call timed out (request_id=%s)", request_id)
        return None
    except Exception as exc:
        logger.warning(
            "LLM call failed: %s (request_id=%s)", type(exc).__name__, request_id
        )
        return None
