"""Ozon search parser using cloakbrowser."""

import asyncio
import html as html_lib
import json
import re
import time
from urllib.parse import quote, urljoin, urlparse

from src.logging_ import logger
from src.modules.search.schemas import SearchSource

from .common import (
    DEFAULT_MAX_PRICE,
    DEFAULT_MIN_PRICE,
    SearchResult,
    append_characteristic,
    append_product,
    build_price_filter,
    encode_query,
    page_content,
    run_site_parser,
    split_product_images,
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
from .typofix import is_plausible_typofix, parse_ozon_typofix, queries_differ

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

_OZON_BASE_URL = "https://www.ozon.ru"
_TILE_GRID_PREFIX = "tileGridDesktop"
_TILE_GRID_SELECTOR = '[data-widget="tileGridDesktop"]'
_OZON_PRODUCT_LINK_SELECTOR = 'a[href*="/product/"]'
_SEARCH_SCROLL_SEC = 2.0
_SEARCH_SCROLL_WHEEL_DELTA_Y = 1400
_SEARCH_SETTLE_TIMEOUT_SEC = 3.0
_SEARCH_SETTLE_POLL_MS = 250
_SEARCH_SETTLE_STABLE_POLLS = 3
_SEARCH_EXTRA_PAGES_BUDGET_SEC = 8.0

_OZON_DOM_UNIQUE_COUNT_JS = f"""() => {{
  const grids = [...document.querySelectorAll('{_TILE_GRID_SELECTOR}')];
  const seen = new Set();
  for (const grid of grids) {{
    for (const anchor of grid.querySelectorAll('a[href*="/product/"]')) {{
      const match = anchor.href.match(/\\/product\\/([^/?#]+)/);
      if (match) {{
        seen.add(match[1]);
      }}
    }}
  }}
  return seen.size;
}}"""

_OZON_DOM_TILES_JS = f"""() => {{
  const grids = [...document.querySelectorAll('{_TILE_GRID_SELECTOR}')];
  const out = [];
  const seen = new Set();
  for (const grid of grids) {{
    for (const tile of grid.querySelectorAll('div.tile-root')) {{
      const anchor = tile.querySelector('a[href*="/product/"]');
      if (!anchor) continue;
      const href = anchor.href;
      const match = href.match(/\\/product\\/([^/?#]+)/);
      if (!match || seen.has(match[1])) continue;
      seen.add(match[1]);
      let name = '';
      let bestLen = 0;
      for (const span of tile.querySelectorAll('span')) {{
        const text = (span.textContent || '').replace(/\\s+/g, ' ').trim();
        if (
          text.length > bestLen
          && text.length > 20
          && !/^\\d/.test(text)
          && text !== 'Оригинал'
          && text !== 'Ozon'
          && text !== 'магазин'
          && text !== 'Lenovo'
        ) {{
          bestLen = text.length;
          name = text;
        }}
      }}
      let price = '';
      for (const span of tile.querySelectorAll('span')) {{
        const text = (span.textContent || '').replace(/\\u2009/g, ' ').trim();
        if (/₽/.test(text) && /\\d/.test(text)) {{
          const digits = text.replace(/\\D/g, '');
          if (digits) {{
            price = digits;
            break;
          }}
        }}
      }}
      let image = '';
      for (const img of tile.querySelectorAll('img')) {{
        let src = img.getAttribute('data-src') || img.getAttribute('src') || '';
        if (!src || src.startsWith('data:')) continue;
        if (src.startsWith('//')) src = 'https:' + src;
        if (
          src.includes('multimedia')
          || src.includes('ir.ozone.ru')
          || src.includes('cdn1.ozon')
        ) {{
          image = src;
          break;
        }}
      }}
      out.push({{ href, name, price, image }});
    }}
  }}
  return out;
}}"""

_OZON_FETCH_PAGE_JS = """async (path) => {
  try {
    const url =
      "https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=" +
      encodeURIComponent(path);
    const response = await fetch(url, {
      credentials: "include",
      headers: { accept: "application/json" },
    });
    const text = await response.text();
    if (!response.ok) {
      return { __ozonError: true, status: response.status, body: text.slice(0, 300) };
    }
    try {
      return JSON.parse(text);
    } catch (error) {
      return { __ozonError: true, status: response.status, body: text.slice(0, 300) };
    }
  } catch (error) {
    return { __ozonError: true, message: String(error) };
  }
}"""


def _decode_product_name(text: str) -> str:
    decoded = text
    for _ in range(3):
        unescaped = html_lib.unescape(decoded)
        if unescaped == decoded:
            break
        decoded = unescaped
    return decoded.replace("\u2009", " ").strip()


def _ozon_product_key(link: str | None) -> str | None:
    if not link:
        return None
    path = urlparse(link).path
    match = re.search(r"/product/([^/?#]+)", path)
    return match.group(1) if match else None


def _products_from_dom_tiles(raw: object) -> list[SearchResult]:
    if not isinstance(raw, list):
        return []
    products: list[SearchResult] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        href = entry.get("href")
        name = entry.get("name")
        if not isinstance(href, str) or not isinstance(name, str) or not name.strip():
            continue
        link = href if href.startswith("http") else urljoin(_OZON_BASE_URL, href)
        price = entry.get("price")
        image = entry.get("image")
        products.append(
            SearchResult(
                name=_decode_product_name(name.strip()),
                product_link=link,
                price=price if isinstance(price, str) and price else None,
                image_link=image if isinstance(image, str) and image.startswith("http") else None,
                image_links=[],
            )
        )
    return products


def _merge_ozon_product(dst: SearchResult, src: SearchResult) -> None:
    if not dst.price and src.price:
        dst.price = src.price
    if not dst.rating and src.rating:
        dst.rating = src.rating
    if not dst.reviews and src.reviews:
        dst.reviews = src.reviews
    if not dst.image_link and src.image_link:
        dst.image_link = src.image_link
        dst.image_links = list(src.image_links)
    elif src.image_links and not dst.image_links:
        dst.image_links = list(src.image_links)
    if not dst.name.strip() and src.name.strip():
        dst.name = src.name


def _merge_ozon_product_lists(
    primary: list[SearchResult],
    extra: list[SearchResult],
    *,
    limit: int | None = None,
) -> list[SearchResult]:
    merged: dict[str, SearchResult] = {}
    for product in primary + extra:
        key = _ozon_product_key(product.product_link)
        if not key:
            continue
        if key not in merged:
            merged[key] = product
        else:
            _merge_ozon_product(merged[key], product)
    items = list(merged.values())
    return items[:limit] if limit and limit > 0 else items


async def _collect_ozon_products_from_dom(page) -> list[SearchResult]:
    raw = await page.evaluate(_OZON_DOM_TILES_JS)
    return _products_from_dom_tiles(raw)


def _append_ozon_product(products: list[SearchResult], item: SearchResult) -> None:
    if item.product_link:
        if any(p.product_link == item.product_link for p in products):
            return
        products.append(item)
        return
    append_product(products, item)


def _ozon_search_page_path(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
    spellcheck: bool = True,
) -> str:
    price_part = build_price_filter(
        "&currency_price=[minPrice].000%3B[maxPrice].000",
        min_price=min_price,
        max_price=max_price,
    )
    if not price_part:
        price_part = "&currency_price=0.000%3B9999999.000"
    deny_category = "false" if spellcheck else "true"
    return (
        f"/search/?deny_category_prediction={deny_category}&force_spell=true"
        f"&text={encode_query(query)}&from_global=true{price_part}&page_changed=true"
    )


def _ozon_api_path(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
    spellcheck: bool = True,
) -> str:
    return quote(
        _ozon_search_page_path(query, min_price=min_price, max_price=max_price, spellcheck=spellcheck),
        safe="",
    )


def _search_api_url(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
    spellcheck: bool = True,
) -> str:
    api_path = _ozon_api_path(query, min_price=min_price, max_price=max_price, spellcheck=spellcheck)
    return f"https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url={api_path}"


def _build_search_url(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
    spellcheck: bool = True,
) -> str:
    encoded = encode_query(query)
    price_part = _ozon_price_path_part(min_price=min_price, max_price=max_price)
    if not spellcheck:
        return (
            f"https://www.ozon.ru/search/?deny_category_prediction=true&force_spell=true"
            f"&text={encoded}&from_global=true{price_part}&page_changed=true"
        )
    return f"https://www.ozon.ru/search/?text={encoded}&from_global=true{price_part}&page_changed=true"


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


def _search_page_actions(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
    spellcheck: bool = True,
) -> list[dict[str, str]]:
    return [
        {
            "type": "url",
            "data": _build_search_url(
                query,
                min_price=min_price,
                max_price=max_price,
                spellcheck=spellcheck,
            ),
        },
        {"type": "waitFor", "data": 'input[name="text"]', "timeout": "20000"},
        {
            "type": "waitFor",
            "data": _OZON_PRODUCT_LINK_SELECTOR,
            "timeout": "20000",
        },
    ]


def _build_actions(
    query: str,
    *,
    geo=None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
    spellcheck: bool = True,
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
            *_search_page_actions(
                query,
                min_price=min_price,
                max_price=max_price,
                spellcheck=spellcheck,
            ),
        ]
    return _search_page_actions(
        query,
        min_price=min_price,
        max_price=max_price,
        spellcheck=spellcheck,
    )


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


def _extract_tile_images(tile_image: object) -> list[str]:
    if not isinstance(tile_image, dict):
        return []
    items = tile_image.get("items")
    if not isinstance(items, list):
        return []
    urls: list[str] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        image = entry.get("image")
        if isinstance(image, dict):
            link = image.get("link")
            if isinstance(link, str) and link.startswith("http"):
                urls.append(link)
    return urls


def _extract_tile_image(tile_image: object) -> str | None:
    images = _extract_tile_images(tile_image)
    return images[0] if images else None


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


def _parse_ozon_json_html(html: str) -> dict | None:
    match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.DOTALL | re.I)
    if not match:
        return None
    raw = match.group(1).strip()
    if not raw.startswith("{"):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_ozon_detail_html(html: str) -> dict[str, str]:
    data = _parse_ozon_json_html(html)
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

    image_link, image_links = split_product_images(_extract_tile_images(item.get("tileImage")))
    return SearchResult(
        name=name,
        product_link=_extract_tile_link(item.get("action")),
        price=_extract_tile_price(main_state),
        image_link=image_link,
        image_links=image_links,
        rating=rating,
        reviews=reviews,
    )


def _parse_ozon_payload(data: object) -> list[SearchResult]:
    if not isinstance(data, dict):
        return []
    products: list[SearchResult] = []
    _parse_widget_states(data, products)
    return products


def _ozon_unescape_path(path: str) -> str:
    return html_lib.unescape(path).replace("&amp;", "&")


def _ozon_extract_next_page_path(data: dict) -> str | None:
    states = data.get("widgetStates")
    if not isinstance(states, dict):
        return None
    for state_id, raw_state in states.items():
        if "infiniteVirtualPaginator" not in state_id or not isinstance(raw_state, str):
            continue
        try:
            state = json.loads(raw_state)
        except json.JSONDecodeError:
            continue
        next_page = state.get("nextPage")
        if isinstance(next_page, str) and next_page.startswith("/"):
            return _ozon_unescape_path(next_page)
    return None


def _merge_ozon_tile_grid_items(base_state: dict, extra_state: dict) -> None:
    for key in ("items", "tiles"):
        base_entries = base_state.get(key)
        extra_entries = extra_state.get(key)
        if not isinstance(base_entries, list) or not isinstance(extra_entries, list):
            continue
        seen = {entry.get("sku") for entry in base_entries if isinstance(entry, dict)}
        for entry in extra_entries:
            if not isinstance(entry, dict):
                continue
            sku = entry.get("sku")
            if sku in seen:
                continue
            seen.add(sku)
            base_entries.append(entry)


def _merge_ozon_search_payload(base: dict, extra: dict) -> None:
    base_states = base.setdefault("widgetStates", {})
    extra_states = extra.get("widgetStates")
    if not isinstance(extra_states, dict):
        return
    for state_id, raw_state in extra_states.items():
        if "infiniteVirtualPaginator" in state_id and isinstance(raw_state, str):
            base_states[state_id] = raw_state
            continue
        if not state_id.startswith(_TILE_GRID_PREFIX) or not isinstance(raw_state, str):
            continue
        if state_id not in base_states:
            base_states[state_id] = raw_state
            continue
        try:
            base_state = json.loads(base_states[state_id])
            extra_state = json.loads(raw_state)
        except json.JSONDecodeError:
            continue
        if isinstance(base_state, dict) and isinstance(extra_state, dict):
            _merge_ozon_tile_grid_items(base_state, extra_state)
            base_states[state_id] = json.dumps(base_state, ensure_ascii=False)


async def _ozon_current_page_path(page) -> str | None:
    path = await page.evaluate(
        """() => {
          const host = window.location.hostname;
          if (!host.includes('ozon.ru')) return '';
          const path = window.location.pathname + window.location.search;
          return path.startsWith('/') ? path : '';
        }"""
    )
    return path if isinstance(path, str) and path.startswith("/") else None


async def _read_ozon_search_query(page) -> str:
    query = await page.evaluate(
        """() => {
          const input = document.querySelector('input[name="text"]');
          if (input && input.value && input.value.trim()) {
            return input.value.trim();
          }
          const params = new URLSearchParams(window.location.search);
          const fromUrl = params.get("text");
          return fromUrl && fromUrl.trim() ? fromUrl.trim() : "";
        }"""
    )
    return query if isinstance(query, str) else ""


async def _ozon_product_tile_count(page) -> int:
    return await page.locator(_OZON_PRODUCT_LINK_SELECTOR).count()


async def _ozon_tile_grid_count(page) -> int:
    return await page.locator(_TILE_GRID_SELECTOR).count()


async def _ozon_dom_unique_product_count(page) -> int:
    count = await page.evaluate(_OZON_DOM_UNIQUE_COUNT_JS)
    return count if isinstance(count, int) else 0


async def _scroll_ozon_search_results(page) -> None:
    deadline = time.monotonic() + _SEARCH_SCROLL_SEC
    while time.monotonic() < deadline:
        await page.mouse.wheel(0, _SEARCH_SCROLL_WHEEL_DELTA_Y)


async def _wait_for_ozon_search_ready(page) -> tuple[int, int]:
    """Wait for lazy tiles; return (unique product slugs in DOM, tile grid count)."""
    deadline = time.monotonic() + _SEARCH_SETTLE_TIMEOUT_SEC
    prev_links = await _ozon_product_tile_count(page)
    prev_grids = await _ozon_tile_grid_count(page)
    stable_polls = 0
    while time.monotonic() < deadline:
        await asyncio.sleep(_SEARCH_SETTLE_POLL_MS / 1000)
        link_count = await _ozon_product_tile_count(page)
        grid_count = await _ozon_tile_grid_count(page)
        if link_count > prev_links or grid_count > prev_grids:
            prev_links = link_count
            prev_grids = grid_count
            stable_polls = 0
            continue
        stable_polls += 1
        if stable_polls >= _SEARCH_SETTLE_STABLE_POLLS:
            break
    return await _ozon_dom_unique_product_count(page), prev_grids


async def _fetch_ozon_search_payload(page, path: str) -> dict | None:
    data = await page.evaluate(_OZON_FETCH_PAGE_JS, path)
    if not isinstance(data, dict):
        return None
    if data.get("__ozonError"):
        logger.warning("Ozon API fetch failed for %r: %s", path[:120], data)
        return None
    return data


async def collect_ozon_products_from_page(
    page,
    *,
    search_query: str,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
    spellcheck: bool = True,
) -> list[SearchResult]:
    await _scroll_ozon_search_results(page)
    dom_unique, grid_count = await _wait_for_ozon_search_ready(page)
    logger.info(
        "Ozon search ready: %d product links in DOM, %d unique across %d tile grids",
        await _ozon_product_tile_count(page),
        dom_unique,
        grid_count,
    )

    query = search_query.strip()
    if not query:
        logger.warning("Ozon: empty search query")
        return []

    if spellcheck:
        query = (await _read_ozon_search_query(page)) or query
        page_path = await _ozon_current_page_path(page)
    else:
        page_path = None

    api_path = page_path or _ozon_search_page_path(
        query,
        min_price=min_price,
        max_price=max_price,
        spellcheck=spellcheck,
    )
    payload = await _fetch_ozon_search_payload(page, api_path)
    if not payload:
        logger.warning("Ozon: search API returned no payload")
        return []

    deadline = time.monotonic() + _SEARCH_EXTRA_PAGES_BUDGET_SEC
    next_path = _ozon_extract_next_page_path(payload)
    extra_fetches = 0
    while next_path and time.monotonic() < deadline:
        parsed = _parse_ozon_payload(payload)
        if dom_unique and len(parsed) >= dom_unique:
            break
        extra = await _fetch_ozon_search_payload(page, next_path)
        if not extra:
            break
        _merge_ozon_search_payload(payload, extra)
        extra_fetches += 1
        next_path = _ozon_extract_next_page_path(extra) or _ozon_extract_next_page_path(payload)

    api_products = _parse_ozon_payload(payload)
    dom_products = await _collect_ozon_products_from_dom(page)
    products = _merge_ozon_product_lists(api_products, dom_products)
    logger.info(
        "Ozon: %d products (%d from API, %d from DOM, %d extra API fetches)",
        len(products),
        len(api_products),
        len(dom_products),
        extra_fetches,
    )
    if not products:
        logger.warning("Ozon: no products in API or DOM after search")
    return products


def parse_html(html: str) -> list[SearchResult]:
    data = _parse_ozon_json_html(html)
    if not data:
        return []
    return _parse_ozon_payload(data)


async def run_ozon_parser(
    context,
    user_input: str,
    *,
    region: str | None = None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
    spellcheck: bool = True,
) -> tuple[SearchSource, str | None]:
    """Run Ozon search and return parsed products."""
    geo = geo_for_marketplace_search(region)
    page_corrected_query: list[str | None] = [None]

    async def run_for_query(query: str):
        async def collect_from_page(page):
            products = await collect_ozon_products_from_page(
                page,
                search_query=query,
                min_price=min_price,
                max_price=max_price,
                spellcheck=spellcheck,
            )
            if spellcheck:
                page_query = await _read_ozon_search_query(page)
                if (
                    page_query
                    and queries_differ(user_input, page_query)
                    and is_plausible_typofix(user_input, page_query)
                ):
                    page_corrected_query[0] = page_query
            return products

        def actions() -> list[dict[str, str]]:
            return _build_actions(
                query,
                geo=geo,
                min_price=min_price,
                max_price=max_price,
                spellcheck=spellcheck,
            )

        return await run_site_parser(
            context,
            site_name=SITE,
            actions=actions,
            parse_html=parse_html,
            parse_typofix=((lambda html: parse_ozon_typofix(html, original=user_input)) if spellcheck else None),
            original_query=user_input,
            check_captcha_expr=CHECK_CAPTCHA,
            headless_env=HEADLESS_ENV,
            enrich_characteristics=_enrich_ozon_characteristics,
            setup_page=make_ozon_setup_page(geo) if geo and geo.ozon_slug else None,
            collect_dom_products=collect_from_page,
        )

    results, timing, typofix = await run_for_query(user_input)

    if (
        spellcheck
        and not typofix
        and page_corrected_query[0]
        and is_plausible_typofix(user_input, page_corrected_query[0])
    ):
        typofix = page_corrected_query[0]

    search_query = typofix if spellcheck and typofix and queries_differ(user_input, typofix) else user_input
    return SearchSource(
        source_type="ozon",
        source_url=_build_search_url(
            search_query,
            min_price=min_price,
            max_price=max_price,
            spellcheck=spellcheck,
        ),
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
