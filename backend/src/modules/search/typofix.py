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


def _search_text_from_json(html: str, original: str | None = None) -> str | None:
    candidates = [_unescape(m) for m in re.findall(r'"searchText"\s*:\s*"([^"\\]+)"', html)]
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if original is None or is_plausible_typofix(original, candidate):
            return candidate
    return None


def _title_search_query(html: str, original: str | None = None) -> str | None:
    match = re.search(r"<title>([^<]+)</title>", html, re.I)
    if not match:
        return None
    title = _unescape(match.group(1))
    for sep in (" — купить", " - купить"):
        if sep in title:
            query = title.split(sep, 1)[0].strip()
            if query and (original is None or is_plausible_typofix(original, query)):
                return query
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


def parse_ozon_typofix(html: str, *, original: str | None = None) -> str | None:
    from src.modules.search.ozon import _extract_json_document

    if captured := _typofix_from_pre(html):
        return captured

    match = re.search(r'"correctedText"\s*:\s*"([^"\\]+)"', html)
    if match:
        corrected = _unescape(match.group(1))
        if corrected and (original is None or is_plausible_typofix(original, corrected)):
            return corrected

    data = _extract_json_document(html)
    if isinstance(data, dict):
        if corrected := _ozon_shared_corrected_text(data):
            if original is None or is_plausible_typofix(original, corrected):
                return corrected
        if corrected := _ozon_search_bar_text(data):
            if original is None or is_plausible_typofix(original, corrected):
                return corrected

    if "fulltextResultsHeader" in html or "Вы искали" in html:
        input_match = re.search(
            r'<input[^>]*name="text"[^>]*value="([^"]+)"',
            html,
            re.I,
        )
        if input_match:
            value = _unescape(input_match.group(1))
            if value and (original is None or is_plausible_typofix(original, value)):
                return value
    return None


def parse_wildberries_typofix(html: str, *, original: str | None = None) -> str | None:
    if captured := _typofix_from_pre(html):
        return captured

    if "searching-results__query-replaced" in html:
        match = re.search(
            r'class="searching-results__query"[^>]*>«([^»]+)»',
            html,
        )
        if match:
            return _unescape(match.group(1)) or None

    input_match = re.search(r'id="searchInput"[^>]*value="([^"]+)"', html, re.I)
    if input_match:
        value = _unescape(input_match.group(1))
        if value and (original is None or is_plausible_typofix(original, value)):
            return value

    title_match = re.search(r'class="searching-results__title">([^<]+)', html)
    if title_match:
        return _unescape(title_match.group(1)) or None
    return None


def queries_differ(original: str, suggestion: str) -> bool:
    return " ".join(original.split()).casefold() != " ".join(suggestion.split()).casefold()


def is_plausible_typofix(original: str, suggestion: str) -> bool:
    if not queries_differ(original, suggestion):
        return False
    original_words = {word.casefold() for word in original.split() if len(word) >= 3}
    suggestion_words = {word.casefold() for word in suggestion.split() if len(word) >= 3}
    return bool(original_words & suggestion_words)


def _query_match_words(query: str) -> list[str]:
    words = [word.casefold() for word in query.split() if len(word) >= 4]
    if words:
        return words
    return [word.casefold() for word in query.split() if len(word) >= 3]


def results_relevant_to_query(query: str, product_names: list[str]) -> bool:
    """True when at least one product name overlaps the query (by word stem)."""
    if not product_names:
        return False
    words = _query_match_words(query)
    if not words:
        return True
    for name in product_names:
        lowered = name.casefold()
        if any(word in lowered for word in words):
            return True
    return False


def parse_yandex_market_typofix(html: str, *, original: str | None = None) -> str | None:
    if captured := _typofix_from_pre(html):
        return captured

    if corrected := _probably_typo_pair(html):
        return corrected

    if corrected := _search_text_from_json(html, original):
        return corrected

    if corrected := _title_search_query(html, original):
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
