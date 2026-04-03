import logging
import re

logger = logging.getLogger(__name__)

UNAVAILABLE_PLACEHOLDER = "[Section unavailable — compliance filter applied]"

COMPLIANCE_PATTERNS: list[re.Pattern] = [
    # Predictive language
    re.compile(r"\blikely\s+to\s+(win|lose|score|succeed|fail)\b", re.IGNORECASE),
    re.compile(r"\bexpected\s+to\b", re.IGNORECASE),
    re.compile(r"\bodds\s+favour\b", re.IGNORECASE),
    re.compile(r"\bprobability\s+of\b", re.IGNORECASE),
    re.compile(r"\bprojected\s+to\b", re.IGNORECASE),
    re.compile(r"\bforecast(ed)?\s+to\b", re.IGNORECASE),
    re.compile(r"\banticipated\s+to\b", re.IGNORECASE),
    re.compile(r"\bpredicted\s+to\b", re.IGNORECASE),
    re.compile(r"\bmore\s+likely\b", re.IGNORECASE),
    re.compile(r"\bless\s+likely\b", re.IGNORECASE),
    re.compile(r"\bhigher\s+chance\b", re.IGNORECASE),
    re.compile(r"\blower\s+chance\b", re.IGNORECASE),
    re.compile(r"\b\d+%\s+chance\b", re.IGNORECASE),
    re.compile(r"\bwill\s+(almost\s+certainly|definitely|probably)\b", re.IGNORECASE),
    # Recommendation language
    re.compile(r"\brecommended\s+bet\b", re.IGNORECASE),
    re.compile(r"\bconsider\s+backing\b", re.IGNORECASE),
    re.compile(r"\bworth\s+backing\b", re.IGNORECASE),
    re.compile(r"\bgood\s+pick\b", re.IGNORECASE),
    re.compile(r"\bstrong\s+case\s+for\b", re.IGNORECASE),
    re.compile(r"\bfavou?rable\s+(pick|choice|bet|option)\b", re.IGNORECASE),
    re.compile(r"\bback\s+(them|him|her|it)\b", re.IGNORECASE),
    # Emotionally charged / absolute language
    re.compile(r"\bdominant\s+(form|side|team|performer)\b", re.IGNORECASE),
    re.compile(r"\bunstoppable\b", re.IGNORECASE),
    re.compile(r"\binevitably\b", re.IGNORECASE),
    re.compile(r"\bsure\s+to\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\s+to\b", re.IGNORECASE),
    re.compile(r"\bcertain\s+to\b", re.IGNORECASE),
    re.compile(r"\bbound\s+to\b", re.IGNORECASE),
    # Outcome ranking
    re.compile(r"\bfavou?rite\b", re.IGNORECASE),
    re.compile(r"\bunderdog\b", re.IGNORECASE),
    re.compile(r"\bhas\s+the\s+(edge|advantage|upper\s+hand)\b", re.IGNORECASE),
    re.compile(r"\bstronger\s+(team|side|performer)\b", re.IGNORECASE),
    re.compile(r"\bweaker\s+(team|side|performer)\b", re.IGNORECASE),
]


def scan_section(text: str) -> list[str]:
    """Returns list of triggered phrase matches. Empty list = PASS."""
    triggers = []
    for pattern in COMPLIANCE_PATTERNS:
        match = pattern.search(text)
        if match:
            triggers.append(match.group(0))
    return triggers


def scan_sections(sections: dict) -> dict[str, list[str]]:
    """Returns {section_name: [triggered_phrases]} for all sections."""
    return {
        key: scan_section(value)
        for key, value in sections.items()
        if isinstance(value, str)
    }


async def run_compliant_pipeline(
    event_title: str,
    event_source: str,
    research_context: str,
    request_id: str = "",
) -> tuple[dict, bool]:
    """
    Runs up to 3 LLM attempts with compliance scanning after each.
    Returns (sections_dict, fully_compliant: bool).
    """
    from src.services.llm_service import assemble_prompt, call_llm, _get_openai_client

    client = _get_openai_client()
    all_attempts: list[dict] = []
    avoid_phrases: list[str] = []

    for attempt in range(1, 4):
        messages = assemble_prompt(
            event_title, event_source, research_context, avoid_phrases or None
        )
        raw = await call_llm(messages, client, request_id)

        if raw is None:
            logger.warning(
                "LLM returned None on attempt %d (request_id=%s)", attempt, request_id
            )
            continue

        all_attempts.append(raw)
        violations = scan_sections(raw)
        has_violations = any(v for v in violations.values())

        if not has_violations:
            return raw, True

        # Collect all triggered phrases for the next retry prompt
        for phrases in violations.values():
            avoid_phrases.extend(phrases)
        avoid_phrases = list(
            dict.fromkeys(avoid_phrases)
        )  # deduplicate, preserve order

        action = "regenerate" if attempt < 3 else "quarantine"
        logger.warning(
            "Compliance violation on attempt %d (action=%s): sections=%s (request_id=%s)",
            attempt,
            action,
            list({k for k, v in violations.items() if v}),
            request_id,
        )

    # All 3 attempts exhausted
    if not all_attempts:
        # LLM itself failed entirely
        placeholder_sections = {
            k: UNAVAILABLE_PLACEHOLDER
            for k in [
                "eventSummary",
                "keyVariables",
                "historicalContext",
                "currentDrivers",
                "riskFactors",
                "dataConfidence",
                "dataGaps",
            ]
        }
        return placeholder_sections, False

    # Per-section quarantine: keep compliant sections, placeholder the rest
    best = all_attempts[-1]
    violations = scan_sections(best)
    quarantined = {}
    for section, triggers in violations.items():
        quarantined[section] = UNAVAILABLE_PLACEHOLDER if triggers else best[section]
    # Ensure all required sections exist
    for key in [
        "eventSummary",
        "keyVariables",
        "historicalContext",
        "currentDrivers",
        "riskFactors",
        "dataConfidence",
        "dataGaps",
    ]:
        if key not in quarantined:
            quarantined[key] = best.get(key, UNAVAILABLE_PLACEHOLDER)

    return quarantined, False
