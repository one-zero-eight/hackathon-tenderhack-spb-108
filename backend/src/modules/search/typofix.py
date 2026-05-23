"""Parse marketplace typo-correction suggestions from search result HTML."""

import html as html_lib
import json
import re

from src.modules.search.common import TYPOFIX_PRE_ID


def _unescape(text: str) -> str:
    return html_lib.unescape(text).replace("\u00a0", " ").strip()


def _typofix_from_pre(html: str) -> str | None:
    match = re.search(
        rf'<pre[^>]*\bid=["\']?{TYPOFIX_PRE_ID}["\']?[^>]*>(.*?)</pre>',
        html,
        re.DOTALL | re.I,
    )
    if not match:
        return None
    text = _unescape(match.group(1))
    return text or None


def _probably_typo_pair(html: str) -> str | None:
    match = re.search(
        r'"old"\s*:\s*"([^"\\]+)"\s*,\s*"new"\s*:\s*"([^"\\]+)"\s*,\s*"probablyTypo"\s*:\s*true',
        html,
    )
    if not match:
        return None
    old, new = _unescape(match.group(1)), _unescape(match.group(2))
    if old and new and old != new:
        return new
    return None


def _ozon_shared_corrected_text(data: dict) -> str | None:
    shared = data.get("shared")
    if isinstance(shared, str):
        try:
            shared = json.loads(shared)
        except json.JSONDecodeError:
            return None
    if not isinstance(shared, dict):
        return None
    catalog = shared.get("catalog")
    if not isinstance(catalog, dict):
        return None
    corrected = catalog.get("correctedText")
    if isinstance(corrected, str) and corrected.strip():
        return _unescape(corrected)
    return None


def _ozon_search_bar_text(data: dict) -> str | None:
    states = data.get("widgetStates")
    if not isinstance(states, dict):
        return None
    for state_id, raw_state in states.items():
        if not state_id.startswith("searchBarDesktop") or not isinstance(raw_state, str):
            continue
        try:
            state = json.loads(raw_state)
        except json.JSONDecodeError:
            continue
        text = state.get("text")
        if isinstance(text, str) and text.strip():
            return _unescape(text)
    return None


def parse_ozon_typofix(html: str) -> str | None:
    from src.modules.search.ozon import _extract_json_document

    match = re.search(r'"correctedText"\s*:\s*"([^"\\]+)"', html)
    if match:
        return _unescape(match.group(1)) or None

    data = _extract_json_document(html)
    if isinstance(data, dict):
        if corrected := _ozon_shared_corrected_text(data):
            return corrected

    if "fulltextResultsHeader" in html or "Вы искали" in html:
        input_match = re.search(
            r'<input[^>]*name="text"[^>]*value="([^"]+)"',
            html,
            re.I,
        )
        if input_match:
            return _unescape(input_match.group(1)) or None
    return None


def parse_wildberries_typofix(html: str) -> str | None:
    if "searching-results__query-replaced" not in html:
        return None
    match = re.search(
        r'class="searching-results__query"[^>]*>«([^»]+)»',
        html,
    )
    if match:
        return _unescape(match.group(1)) or None
    title_match = re.search(r'class="searching-results__title">([^<]+)', html)
    if title_match:
        return _unescape(title_match.group(1)) or None
    return None


def queries_differ(original: str, suggestion: str) -> bool:
    return " ".join(original.split()).casefold() != " ".join(suggestion.split()).casefold()


def parse_yandex_market_typofix(html: str) -> str | None:
    if captured := _typofix_from_pre(html):
        return captured

    if corrected := _probably_typo_pair(html):
        return corrected

    if "SearchSpellchecker" in html or "Запрос исправлен" in html:
        match = re.search(
            r'data-auto="wrong"[^>]*>.*?«([^»]+)»',
            html,
            re.DOTALL,
        )
        if match:
            wrong = _unescape(match.group(1))
            for text_match in re.finditer(r'"text"\s*:\s*"([^"\\]+)"', html):
                candidate = _unescape(text_match.group(1))
                if candidate and candidate != wrong:
                    return candidate
    return None
