import asyncio
import json
import logging

from openai import AsyncOpenAI

from src.core.config import settings

logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
LLM_TIMEOUT_SECONDS = 8.0

SYSTEM_PROMPT = (
    "You are a neutral research analyst. Your sole role is to surface "
    "factual, structured information about the event provided. You must not make predictions, "
    "issue recommendations, suggest probabilities, rank outcomes by likelihood, or use "
    "persuasive or emotionally charged language of any kind. Every section must be written "
    "in plain, balanced, factual prose."
)

SECTION_INSTRUCTIONS = """\
Return your response as a JSON object with exactly these keys:
{
  "eventSummary": "...",
  "keyVariables": "...",
  "historicalContext": "...",
  "currentDrivers": "...",
  "riskFactors": "...",
  "dataConfidence": "...",
  "dataGaps": "..."
}

Definitions:
- eventSummary: What the event is, who/what is involved, when and where it takes place.
- keyVariables: Objective factors that are relevant to the event (form, fitness, conditions, etc.).
- historicalContext: Past encounters, trends, or statistical record — stated as facts.
- currentDrivers: Recent developments, news, or circumstances relevant to this event.
- riskFactors: Uncertainties, unknowns, or factors that could change outcomes — neutral.
- dataConfidence: Assess the quality and recency of available data. No predictions.
- dataGaps: Identify what information is missing or unavailable."""

NEGATIVE_CONSTRAINTS = """\
DO NOT use any of the following:
- Predictive language: "likely", "expected to", "odds favour", "probability of", "projected", "forecast", "anticipated"
- Recommendation language: "consider backing", "worth backing", "recommended", "favourable", "strong case for"
- Emotionally charged phrases: "dominant", "unstoppable", "inevitably", "sure to", "guaranteed"
- Any language that implies one outcome is more probable than another."""

REQUIRED_KEYS = {
    "eventSummary",
    "keyVariables",
    "historicalContext",
    "currentDrivers",
    "riskFactors",
    "dataConfidence",
    "dataGaps",
}


def assemble_prompt(
    event_title: str,
    event_source: str,
    research_context: str,
    avoid_phrases: list[str] | None = None,
) -> list[dict]:
    context_block = (
        research_context
        if research_context
        else "[No external data available — use only general knowledge.]"
    )
    avoid_block = ""
    if avoid_phrases:
        avoid_block = (
            "\n\nAdditional constraint — avoid these specific phrases from your last attempt:\n"
            + "\n".join(f"- {p}" for p in avoid_phrases)
        )

    user_content = (
        f"Event: {event_title}\n"
        f"Detected on: {event_source}\n\n"
        f"Research context:\n{context_block}\n\n"
        f"{SECTION_INSTRUCTIONS}\n\n"
        f"{NEGATIVE_CONSTRAINTS}"
        f"{avoid_block}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def call_llm(
    messages: list[dict],
    client: AsyncOpenAI | None = None,
    request_id: str = "",
) -> dict | None:
    """Returns parsed sections dict, or None on any failure."""
    if client is None:
        client = _get_openai_client()
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=2000,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        # Validate all required keys are present
        if not REQUIRED_KEYS.issubset(parsed.keys()):
            logger.warning(
                "LLM response missing required keys: %s (request_id=%s)",
                REQUIRED_KEYS - parsed.keys(),
                request_id,
            )
            return None
        return {k: str(parsed[k]) for k in REQUIRED_KEYS}
    except asyncio.TimeoutError:
        logger.warning("LLM call timed out (request_id=%s)", request_id)
        return None
    except Exception as exc:
        logger.warning(
            "LLM call failed: %s (request_id=%s)", type(exc).__name__, request_id
        )
        return None
