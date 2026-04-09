import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from openai import AsyncOpenAI

from src.core.config import settings
from src.services.llm.prompts import REQUIRED_KEYS, SECTION_INSTRUCTIONS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
LLM_TIMEOUT_SECONDS = 60.0
SECTION_ORDER = (
    "eventSummary",
    "keyVariables",
    "historicalContext",
    "currentDrivers",
    "riskFactors",
    "dataConfidence",
    "dataGaps",
)

SectionDeltaCallback = Callable[[dict[str, Any]], Awaitable[None]]


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
        f"{SECTION_INSTRUCTIONS}\n\n"
        "Search the web for the latest information on this event before responding. "
        "Then use the submit_research_sections function for the final answer."
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
    section_callback: SectionDeltaCallback | None = None,
) -> dict[str, str] | None:
    """Assembles the prompt and calls the LLM. Returns sections dict or None on failure."""
    messages = assemble_prompt(event_title, event_source, research_context)
    client = _get_openai_client()
    return await call_llm(
        messages,
        client,
        request_id,
        section_callback=section_callback,
    )


def _get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _build_web_search_tool() -> dict[str, Any] | None:
    if not settings.OPENAI_WEB_SEARCH_ENABLED:
        return None

    return {
        "type": "web_search_preview"
    }


def _build_sections_function_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "name": "submit_research_sections",
        "description": (
            "Submit the final structured research output after considering the "
            "provided context and any web search findings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                key: {
                    "type": "string",
                    "description": f"Final research content for {key}.",
                }
                for key in SECTION_ORDER
            },
            "required": list(SECTION_ORDER),
            "additionalProperties": False,
        },
        "strict": True,
    }


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


def _extract_function_arguments_from_final_response(response: Any) -> str:
    for output_item in getattr(response, "output", []) or []:
        if getattr(output_item, "type", "") != "function_call":
            continue
        if getattr(output_item, "name", "") != "submit_research_sections":
            continue
        arguments = getattr(output_item, "arguments", "")
        if arguments:
            return str(arguments).strip()
    return ""


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


def _read_json_string_prefix(raw_text: str, start_index: int) -> tuple[str, bool]:
    characters: list[str] = []
    cursor = start_index

    while cursor < len(raw_text):
        char = raw_text[cursor]
        if char == "\\":
            if cursor + 1 >= len(raw_text):
                break

            escape = raw_text[cursor + 1]
            escape_map = {
                '"': '"',
                "\\": "\\",
                "/": "/",
                "b": "\b",
                "f": "\f",
                "n": "\n",
                "r": "\r",
                "t": "\t",
            }
            if escape == "u":
                if cursor + 5 >= len(raw_text):
                    break
                codepoint = raw_text[cursor + 2 : cursor + 6]
                try:
                    characters.append(chr(int(codepoint, 16)))
                except ValueError:
                    return "".join(characters), False
                cursor += 6
                continue

            characters.append(escape_map.get(escape, escape))
            cursor += 2
            continue

        if char == '"':
            return "".join(characters), True

        characters.append(char)
        cursor += 1

    return "".join(characters), False


def _extract_partial_sections(raw_text: str) -> dict[str, dict[str, Any]]:
    partial_sections: dict[str, dict[str, Any]] = {}

    for key in SECTION_ORDER:
        key_pattern = f'"{key}"'
        key_index = raw_text.find(key_pattern)
        if key_index == -1:
            continue

        cursor = key_index + len(key_pattern)
        while cursor < len(raw_text) and raw_text[cursor].isspace():
            cursor += 1

        if cursor >= len(raw_text) or raw_text[cursor] != ":":
            continue

        cursor += 1
        while cursor < len(raw_text) and raw_text[cursor].isspace():
            cursor += 1

        if cursor >= len(raw_text) or raw_text[cursor] != '"':
            continue

        value, done = _read_json_string_prefix(raw_text, cursor + 1)
        partial_sections[key] = {"content": value, "done": done}

    return partial_sections


async def _emit_section_deltas(
    raw_text: str,
    section_callback: SectionDeltaCallback | None,
    emitted_content: dict[str, str],
    emitted_done: dict[str, bool],
) -> None:
    if section_callback is None:
        return

    partial_sections = _extract_partial_sections(raw_text)
    for key in SECTION_ORDER:
        state = partial_sections.get(key)
        if state is None:
            continue

        content = str(state["content"])
        done = bool(state["done"])
        previous_content = emitted_content.get(key, "")
        previous_done = emitted_done.get(key, False)
        if content == previous_content and done == previous_done:
            continue

        delta = (
            content[len(previous_content) :]
            if content.startswith(previous_content)
            else content
        )
        emitted_content[key] = content
        emitted_done[key] = done

        await section_callback(
            {
                "section": key,
                "delta": delta,
                "content": content,
                "done": done,
            }
        )


async def call_llm(
    messages: list[dict[str, Any]],
    client: AsyncOpenAI | None = None,
    request_id: str = "",
    section_callback: SectionDeltaCallback | None = None,
) -> dict[str, str] | None:
    """Returns parsed sections dict, or None on any failure."""
    if client is None:
        client = _get_openai_client()

    instructions, input_payload = _messages_to_responses_payload(messages)

    try:
        text_chunks: list[str] = []
        done_text = ""
        function_args_chunks: list[str] = []
        done_function_args = ""
        final_response: Any = None
        emitted_content: dict[str, str] = {}
        emitted_done: dict[str, bool] = {}
        tools: list[dict[str, Any]] = [_build_sections_function_tool()]
        web_search_tool = _build_web_search_tool()
        if web_search_tool is not None:
            tools.append(web_search_tool)

        async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
            async with client.responses.stream(
                model=MODEL,
                input=input_payload,
                instructions=instructions,
                temperature=0.2,
                max_output_tokens=2000,
                tools=tools,
                tool_choice="auto",
            ) as stream:
                async for event in stream:
                    if event.type == "response.function_call_arguments.delta":
                        function_args_chunks.append(event.delta)
                        await _emit_section_deltas(
                            "".join(function_args_chunks),
                            section_callback,
                            emitted_content,
                            emitted_done,
                        )
                    elif event.type == "response.function_call_arguments.done":
                        item = getattr(event, "item", None)
                        done_function_args = str(getattr(item, "arguments", "") or "")
                        await _emit_section_deltas(
                            done_function_args,
                            section_callback,
                            emitted_content,
                            emitted_done,
                        )
                    elif event.type == "response.output_text.delta":
                        text_chunks.append(event.delta)
                        await _emit_section_deltas(
                            "".join(text_chunks),
                            section_callback,
                            emitted_content,
                            emitted_done,
                        )
                    elif event.type == "response.output_text.done":
                        done_text = event.text
                        await _emit_section_deltas(
                            done_text,
                            section_callback,
                            emitted_content,
                            emitted_done,
                        )

                final_response = await stream.get_final_response()

        content = "".join(function_args_chunks).strip()
        if not content:
            content = done_function_args.strip()
        if not content and final_response is not None:
            content = _extract_function_arguments_from_final_response(final_response)
        if not content:
            content = "".join(text_chunks).strip()
        if not content:
            content = done_text.strip()
        if not content and final_response is not None:
            content = _extract_text_from_final_response(final_response)

        if not content:
            logger.warning("LLM stream produced no content (request_id=%s)", request_id)
            return None

        await _emit_section_deltas(
            content,
            section_callback,
            emitted_content,
            emitted_done,
        )

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

        return {key: str(parsed[key]) for key in SECTION_ORDER}

    except TimeoutError:
        logger.warning("LLM call timed out (request_id=%s)", request_id)
        return None
    except Exception as exc:
        logger.warning(
            "LLM call failed: %s: %s (request_id=%s)",
            type(exc).__name__,
            exc,
            request_id,
        )
        return None
