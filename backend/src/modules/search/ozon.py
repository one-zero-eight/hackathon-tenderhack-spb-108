"""Ozon search parser using cloakbrowser."""

import html as html_lib
import json
import re
from urllib.parse import quote, urljoin, urlparse

from src.modules.search.schemas import SearchSource

from .common import (
    DEFAULT_MAX_PRICE,
    DEFAULT_MIN_PRICE,
    RESULT_PRE_ID,
    TYPOFIX_PRE_ID,
    SearchResult,
    append_characteristic,
    append_product,
    build_price_filter,
    collect_products,
    encode_query,
    extract_pre_content,
    page_content,
    parse_result_pre,
    run_site_parser,
)
from .details import enrich_product_characteristics
from .region_geo import (
    _OZON_BOOTSTRAP_URL,
    geo_for_marketplace_search,
    make_ozon_setup_page,
    ozon_confirm_region_script,
    ozon_geo_page_url,
    ozon_region_already_set_check,
    ozon_set_region_script,
)
from .typofix import parse_ozon_typofix, queries_differ

SITE = "ozon"
CHECK_CAPTCHA = (
    "(() => {"
    " if (document.querySelector('#reload-button') != null) {"
    "   document.querySelector('#reload-button').click();"
    " }"
    " return document.getElementById('challenge-stage') != null"
    "   || (document.querySelector('h1') != null"
    "       && document.querySelector('h1').textContent.indexOf('ограничен') != -1);"
    "})()"
)
HEADLESS_ENV = "OZON_HEADLESS"

_PRODUCT_KEYS = ("skuId", "sku", "cellTrackingInfo", "tileImage")
_OZON_BASE_URL = "https://www.ozon.ru"
_TILE_GRID_PREFIX = "tileGridDesktop"


def _decode_product_name(text: str) -> str:
    decoded = text
    for _ in range(3):
        unescaped = html_lib.unescape(decoded)
        if unescaped == decoded:
            break
        decoded = unescaped
    return decoded.replace("\u2009", " ").strip()


def _append_ozon_product(products: list[SearchResult], item: SearchResult) -> None:
    if item.product_link:
        if any(p.product_link == item.product_link for p in products):
            return
        products.append(item)
        return
    append_product(products, item)


def _ozon_api_path(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> str:
    price_part = build_price_filter(
        "&currency_price=[minPrice].000%3B[maxPrice].000",
        min_price=min_price,
        max_price=max_price,
    )
    if not price_part:
        price_part = "&currency_price=0.000%3B9999999.000"
    path = (
        f"/search/?deny_category_prediction=false&force_spell=true"
        f"&text={encode_query(query)}&from_global=true{price_part}&page_changed=true"
    )
    return quote(path, safe="")


def _search_api_url(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> str:
    api_path = _ozon_api_path(query, min_price=min_price, max_price=max_price)
    return f"https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url={api_path}"


def _build_search_url(query: str) -> str:
    encoded = encode_query(query)
    return f"https://www.ozon.ru/search/?text={encoded}&from_global=true"


def _ozon_price_path_part(
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> str:
    price_part = build_price_filter(
        "&currency_price=[minPrice].000%3B[maxPrice].000",
        min_price=min_price,
        max_price=max_price,
    )
    if not price_part:
        return "&currency_price=0.000%3B9999999.000"
    return price_part


_OZON_FETCH_TEMPLATE = r"""const originalQuery = __ORIGINAL_QUERY__;

function normalizeQuery(text) {
  return (text || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

function resolveCorrectedQuery() {
  const correctedMatch = document.documentElement.innerHTML.match(
    /"correctedText"\s*:\s*"([^"\\]+)"/
  );
  if (correctedMatch) {
    const corrected = correctedMatch[1];
    if (normalizeQuery(corrected) !== normalizeQuery(originalQuery)) {
      return corrected;
    }
  }
  const input = document.querySelector('input[name="text"]');
  if (input && input.value) {
    const value = input.value.trim();
    if (value && normalizeQuery(value) !== normalizeQuery(originalQuery)) {
      return value;
    }
  }
  return originalQuery;
}

async function waitAndFetch() {
  let corrected = originalQuery;
  for (let attempt = 0; attempt < 24; attempt++) {
    corrected = resolveCorrectedQuery();
    if (normalizeQuery(corrected) !== normalizeQuery(originalQuery)) {
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  const pricePart = __PRICE_PART__;
  const path =
    '/search/?deny_category_prediction=false&force_spell=true&text=' +
    encodeURIComponent(corrected) +
    '&from_global=true' +
    pricePart +
    '&page_changed=true';
  const apiUrl =
    'https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=' +
    encodeURIComponent(path);

  const response = await fetch(apiUrl, {
    credentials: 'include',
    headers: { accept: 'application/json' },
  });
  const data = await response.text();

  document.body = document.createElement('body');
  if (normalizeQuery(corrected) !== normalizeQuery(originalQuery)) {
    const typoPre = document.createElement('pre');
    typoPre.id = "__TYPOFIX_PRE_ID__";
    typoPre.innerText = corrected;
    document.body.append(typoPre);
  }
  const resultPre = document.createElement('pre');
  resultPre.id = "__PRE_ID__";
  resultPre.innerText = data;
  document.body.append(resultPre);
  return true;
}

return await waitAndFetch();"""


def _build_fetch_script(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> str:
    return (
        _OZON_FETCH_TEMPLATE.replace("__ORIGINAL_QUERY__", json.dumps(query))
        .replace("__PRICE_PART__", json.dumps(_ozon_price_path_part(min_price=min_price, max_price=max_price)))
        .replace("__PRE_ID__", RESULT_PRE_ID)
        .replace("__TYPOFIX_PRE_ID__", TYPOFIX_PRE_ID)
    )


def _search_page_actions(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> list[dict[str, str]]:
    return [
        {"type": "url", "data": _build_search_url(query)},
        {"type": "waitFor", "data": 'input[name="text"]', "timeout": "20000"},
        {
            "type": "waitElement",
            "data": _build_fetch_script(query, min_price=min_price, max_price=max_price),
            "wait_for": f"pre#{RESULT_PRE_ID}",
        },
    ]


def _build_actions(
    query: str,
    *,
    geo=None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> list[dict[str, str]]:
    geo_page = ozon_geo_page_url(geo) if geo else None
    if geo and geo.ozon_slug and geo_page:
        return [
            {"type": "url", "data": _OZON_BOOTSTRAP_URL},
            {"type": "wait", "data": "500"},
            {"type": "waitElement", "data": ozon_set_region_script(geo), "wait_for": ""},
            {
                "type": "skipIf",
                "data": ozon_region_already_set_check(geo),
                "skip_count": "3",
            },
            {"type": "url", "data": geo_page},
            {"type": "wait", "data": "800"},
            {"type": "waitElement", "data": ozon_confirm_region_script(geo), "wait_for": ""},
            *_search_page_actions(query, min_price=min_price, max_price=max_price),
        ]
    return _search_page_actions(query, min_price=min_price, max_price=max_price)


def _parse_widget_states(data: dict, products: list[SearchResult]) -> None:
    states = data.get("widgetStates")
    if not isinstance(states, dict):
        return
    for state_id, raw_state in states.items():
        if not state_id.startswith(_TILE_GRID_PREFIX) or not isinstance(raw_state, str):
            continue
        try:
            state = json.loads(raw_state)
        except json.JSONDecodeError:
            continue
        _parse_tile_grid_state(state, products)


def _parse_tile_grid_state(state: dict, products: list[SearchResult]) -> None:
    for key in ("items", "tiles"):
        entries = state.get(key)
        if not isinstance(entries, list):
            continue
        for item in entries:
            parsed = _parse_ozon_tile(item)
            if parsed:
                _append_ozon_product(products, parsed)


def _extract_tile_name(main_state: list) -> str | None:
    fallback: str | None = None
    for block in main_state:
        if not isinstance(block, dict) or block.get("type") != "textAtom":
            continue
        text_atom = block.get("textAtom", {})
        if not isinstance(text_atom, dict):
            continue
        text = text_atom.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        decoded = _decode_product_name(text)
        if block.get("id") == "name":
            return decoded
        fallback = decoded
    return fallback


def _extract_tile_price(main_state: list) -> str | None:
    for block in main_state:
        if not isinstance(block, dict) or block.get("type") != "priceV2":
            continue
        prices = block.get("priceV2", {}).get("price", [])
        if not isinstance(prices, list):
            continue
        for entry in prices:
            if not isinstance(entry, dict):
                continue
            if entry.get("textStyle") not in (None, "PRICE", "CARD_PRICE"):
                continue
            text = entry.get("text")
            if isinstance(text, str) and text.strip():
                digits = re.sub(r"\D", "", text)
                return digits or text.strip()
        if prices and isinstance(prices[0], dict):
            text = prices[0].get("text")
            if isinstance(text, str) and text.strip():
                digits = re.sub(r"\D", "", text)
                return digits or text.strip()
    return None


def _extract_tile_image(tile_image: object) -> str | None:
    if not isinstance(tile_image, dict):
        return None
    items = tile_image.get("items")
    if not isinstance(items, list):
        return None
    for entry in items:
        if not isinstance(entry, dict):
            continue
        image = entry.get("image")
        if isinstance(image, dict):
            link = image.get("link")
            if isinstance(link, str) and link.startswith("http"):
                return link
    return None


def _extract_tile_link(action: object) -> str | None:
    if not isinstance(action, dict):
        return None
    link = action.get("link")
    if not isinstance(link, str) or not link.strip():
        return None
    if link.startswith("http"):
        return link
    return urljoin(_OZON_BASE_URL, link)


def _parse_ozon_spec_entry(specs: dict[str, str], entry: dict) -> None:
    title = entry.get("title")
    if isinstance(title, dict):
        title_parts = title.get("textRs", [])
        name = next(
            (part.get("content") for part in title_parts if isinstance(part, dict) and part.get("content")),
            None,
        )
    else:
        name = entry.get("name")
    values = entry.get("values", [])
    texts = [v.get("text") for v in values if isinstance(v, dict) and v.get("text")]
    if name and texts:
        append_characteristic(specs, str(name), ", ".join(texts))


def _parse_ozon_characteristic_state(state: dict) -> dict[str, str]:
    specs: dict[str, str] = {}
    for item in state.get("characteristics", []):
        if not isinstance(item, dict):
            continue
        if "short" in item or "long" in item:
            for section in ("short", "long"):
                for entry in item.get(section, []):
                    if isinstance(entry, dict):
                        _parse_ozon_spec_entry(specs, entry)
            continue
        _parse_ozon_spec_entry(specs, item)
    return specs


def parse_ozon_detail_html(html: str) -> dict[str, str]:
    data = _extract_json_document(html)
    if not data:
        return {}
    specs: dict[str, str] = {}
    for state_id, raw_state in data.get("widgetStates", {}).items():
        if "haracteristic" not in state_id.lower() or not isinstance(raw_state, str):
            continue
        try:
            state = json.loads(raw_state)
        except json.JSONDecodeError:
            continue
        for key, value in _parse_ozon_characteristic_state(state).items():
            append_characteristic(specs, key, value)
    return specs


def _ozon_detail_api_url(product_link: str) -> str:
    path = urlparse(product_link).path
    return f"{_OZON_BASE_URL}/api/entrypoint-api.bx/page/json/v2?url={quote(path, safe='')}"


def _ozon_features_api_url(product_link: str) -> str:
    path = urlparse(product_link).path.rstrip("/") + "/features/"
    return f"{_OZON_BASE_URL}/api/entrypoint-api.bx/page/json/v2?url={quote(path, safe='')}"


async def _load_ozon_api_specs(page, api_url: str) -> dict[str, str]:
    await page.goto(api_url, wait_until="domcontentloaded", timeout=30_000)
    await page.wait_for_timeout(1000)
    return parse_ozon_detail_html(await page_content(page))


async def fetch_ozon_detail_characteristics(page, product_link: str) -> dict[str, str]:
    specs = await _load_ozon_api_specs(page, _ozon_features_api_url(product_link))
    if len(specs) >= 10:
        return specs
    short_specs = await _load_ozon_api_specs(page, _ozon_detail_api_url(product_link))
    merged = dict(short_specs)
    for key, value in specs.items():
        append_characteristic(merged, key, value)
    return merged


async def _enrich_ozon_characteristics(page, products: list[SearchResult]) -> None:
    await enrich_product_characteristics(
        page,
        products,
        fetch_characteristics=fetch_ozon_detail_characteristics,
        check_captcha_expr=CHECK_CAPTCHA,
        site_name=SITE,
    )


def _parse_ozon_tile(item: object) -> SearchResult | None:
    if not isinstance(item, dict) or not item.get("sku"):
        return None

    main_state = item.get("mainState")
    if not isinstance(main_state, list):
        return None

    name = _extract_tile_name(main_state)
    if not name:
        return None

    rating: str | None = None
    reviews: str | None = None
    for block in main_state:
        if not isinstance(block, dict) or block.get("type") != "labelListV2":
            continue
        labels = block.get("labelListV2", {}).get("items", [])
        if not isinstance(labels, list):
            continue
        for label in labels:
            if not isinstance(label, dict) or label.get("type") != "text":
                continue
            text = label.get("text", {}).get("text", "")
            if not isinstance(text, str):
                continue
            cleaned = html_lib.unescape(text).replace("\xa0", " ").strip()
            if rating is None and re.fullmatch(r"\d+([.,]\d+)?", cleaned):
                rating = cleaned
            elif reviews is None and "отзыв" in cleaned.lower():
                reviews = cleaned

    return SearchResult(
        name=name,
        product_link=_extract_tile_link(item.get("action")),
        price=_extract_tile_price(main_state),
        image_link=_extract_tile_image(item.get("tileImage")),
        rating=rating,
        reviews=reviews,
    )


def _parse_ozon_payload(data: object) -> list[SearchResult]:
    products: list[SearchResult] = []
    if not isinstance(data, dict):
        return products

    _parse_widget_states(data, products)
    if products:
        return products

    collect_products(data, set(), products, product_keys=_PRODUCT_KEYS)
    return products


def _extract_json_document(html: str) -> dict | None:
    for candidate in (
        extract_pre_content(html),
        _extract_any_pre_json(html),
        _extract_body_json(html),
    ):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _extract_any_pre_json(html: str) -> str | None:
    match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.DOTALL | re.I)
    if match:
        text = match.group(1).strip()
        if text.startswith("{"):
            return text
    return None


def _extract_body_json(html: str) -> str | None:
    stripped = html.strip()
    if stripped.startswith("{"):
        return stripped
    match = re.search(r"<body[^>]*>\s*(\{.*\})\s*</body>", html, re.DOTALL | re.I)
    if match:
        return match.group(1).strip()
    return None


def parse_html(html: str) -> list[SearchResult]:
    raw = extract_pre_content(html)
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            ozon_products = _parse_ozon_payload(data)
            if ozon_products:
                return ozon_products

    data = _extract_json_document(html)
    if data:
        ozon_products = _parse_ozon_payload(data)
        if ozon_products:
            return ozon_products

    return parse_result_pre(html, product_keys=_PRODUCT_KEYS)


async def run_ozon_parser(
    context,
    user_input: str,
    *,
    region: str | None = None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> tuple[SearchSource, str | None]:
    """Run Ozon search and return parsed products."""
    geo = geo_for_marketplace_search(region)

    async def run_for_query(query: str):
        def actions() -> list[dict[str, str]]:
            return _build_actions(query, geo=geo, min_price=min_price, max_price=max_price)

        return await run_site_parser(
            context,
            site_name=SITE,
            actions=actions,
            parse_html=parse_html,
            parse_typofix=lambda html: parse_ozon_typofix(html, original=user_input),
            original_query=user_input,
            check_captcha_expr=CHECK_CAPTCHA,
            headless_env=HEADLESS_ENV,
            enrich_characteristics=_enrich_ozon_characteristics,
            setup_page=make_ozon_setup_page(geo) if geo and geo.ozon_slug else None,
        )

    # Fetch script already applies Ozon correctedText before API call — one browser run is enough.
    results, timing, typofix = await run_for_query(user_input)

    search_query = typofix if typofix and queries_differ(user_input, typofix) else user_input
    return SearchSource(
        source_type="ozon",
        source_url=_build_search_url(search_query),
        source_title="Ozon",
        source_favicon_url=None,
        results=results,
        timing=timing,
    ), typofix


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "tasty coffee в зернах"
    results = run_ozon_parser(query)
    print(results.model_dump_json(ensure_ascii=False))
