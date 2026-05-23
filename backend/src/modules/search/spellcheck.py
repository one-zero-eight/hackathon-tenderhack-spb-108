import os

import httpx

from src.config import settings
from src.logging_ import logger
from src.modules.search.schemas import SpellcheckLanguage

SPELLCHECK_TIMEOUT_SECONDS = float(os.getenv("LANGUAGETOOL_TIMEOUT_SECONDS", "5"))
MAX_SPELLCHECK_SUGGESTIONS = 3


def parse_spellcheck_suggestions(payload: dict, original_word: str) -> list[str]:
    suggestions: list[str] = []
    seen: set[str] = set()

    for match in payload.get("matches", []):
        if not isinstance(match, dict):
            continue

        for replacement in match.get("replacements", []):
            if not isinstance(replacement, dict):
                continue

            candidate = replacement.get("value")
            if not isinstance(candidate, str):
                continue

            normalized = candidate.strip()
            if not normalized:
                continue

            if normalized.casefold() == original_word.casefold():
                continue

            candidate_key = normalized.casefold()
            if candidate_key in seen:
                continue

            seen.add(candidate_key)
            suggestions.append(normalized)
            if len(suggestions) >= MAX_SPELLCHECK_SUGGESTIONS:
                return suggestions

    return suggestions


async def fetch_spellcheck_suggestions(word: str, language: SpellcheckLanguage) -> list[str]:
    try:
        async with httpx.AsyncClient(
            base_url=settings.languagetool_base_url,
            timeout=SPELLCHECK_TIMEOUT_SECONDS,
        ) as client:
            response = await client.post(
                "/v2/check",
                data={
                    "text": word,
                    "language": language.value,
                },
            )
            response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("LanguageTool spellcheck request failed for %r", word, exc_info=True)
        return []

    payload = response.json()
    if not isinstance(payload, dict):
        return []

    return parse_spellcheck_suggestions(payload, word)
