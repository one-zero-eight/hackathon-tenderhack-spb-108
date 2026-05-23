"""Shared utilities for marketplace search parsers."""

import asyncio
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote_plus, urljoin

from cloakbrowser import launch_persistent_context_async

from src.logging_ import logger
from src.modules.search.schemas import SearchResult

RESULT_PRE_ID = "d405f4e66468fd64bd88c8f16681286a"
HTTP_PROXY: str | None = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
DEFAULT_MIN_PRICE = 0
DEFAULT_MAX_PRICE = 9_999_999
SEARCH_HEADLESS_ENV = "SEARCH_HEADLESS"


class _BrowserState:
    context = None


_browser_lock = asyncio.Lock()


async def get_browser_context():
    async with _browser_lock:
        if _BrowserState.context is not None:
            return _BrowserState.context
        session_dir, _ = site_paths("shared")
        session_dir.mkdir(parents=True, exist_ok=True)
        headless = headless_from_env(SEARCH_HEADLESS_ENV)
        if HTTP_PROXY:
            logger.info("Using HTTP proxy: %s", HTTP_PROXY.split("@")[-1])
        _BrowserState.context = await launch_persistent_context_async(
            user_data_dir=session_dir,
            headless=headless,
            proxy=HTTP_PROXY,
            locale="ru-RU",
        )
        logger.info("Shared cloakbrowser context started (headless=%s)", headless)
        return _BrowserState.context


async def close_browser_context() -> None:
    async with _browser_lock:
        if _BrowserState.context is None:
            return
        await _BrowserState.context.close()
        _BrowserState.context = None
        logger.info("Shared cloakbrowser context closed")


def scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def site_paths(site: str) -> tuple[Path, Path]:
    base = scripts_dir() / "out" / site
    return base / "session", base / "html"


def headless_from_env(var_name: str) -> bool:
    return os.environ.get(var_name, "0") == "1"


def build_price_filter(
    template: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> str:
    if min_price <= 0 and max_price >= DEFAULT_MAX_PRICE:
        return ""
    return template.replace("[minPrice]", str(min_price)).replace("[maxPrice]", str(max_price))


def encode_query(query: str) -> str:
    return quote_plus(query)


def append_product(products: list[SearchResult], item: SearchResult | None) -> None:
    if item is None:
        return
    if any(p.name == item.name and p.price == item.price for p in products):
        return
    products.append(item)


def save_html(out_dir: Path, step: int, html: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"step_{step:02d}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("Saved HTML to %s", path)
    return path


async def page_content(page) -> str:
    for attempt in range(6):
        try:
            return await page.content()
        except Exception as exc:
            if "navigating" not in str(exc).lower() or attempt >= 5:
                raise
            await page.wait_for_load_state("domcontentloaded", timeout=15_000)
            await page.wait_for_timeout(500)
    return await page.content()


def extract_pre_content(html: str, pre_id: str = RESULT_PRE_ID) -> str | None:
    match = re.search(
        rf'<pre[^>]*id="{re.escape(pre_id)}"[^>]*>(.*?)</pre>',
        html,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return None


async def check_captcha(page, expression: str, site_name: str) -> bool:
    detected = await page.evaluate(f"() => Boolean({expression})")
    if detected:
        logger.warning("Captcha on %s — solve it in the browser window", site_name)
    else:
        logger.info("Captcha not detected on %s", site_name)
    return detected


async def wait_captcha_solved(page, expression: str, timeout_ms: int = 300_000) -> None:
    await page.wait_for_function(f"() => !({expression})", timeout=timeout_ms)
    logger.info("Captcha cleared, continuing")


async def run_action(
    page,
    action: dict[str, str],
    step: int,
    *,
    out_dir: Path,
    check_captcha_expr: str,
    site_name: str,
) -> None:
    action_type = action["type"]
    data = action["data"]
    wait_for = action.get("wait_for", f"pre#{RESULT_PRE_ID}")

    if action_type == "url":
        await page.goto(data, wait_until="domcontentloaded", timeout=60_000)
    elif action_type == "wait":
        await page.wait_for_timeout(int(data))
    elif action_type == "waitElement":
        await page.evaluate(f"async () => {{ {data} }}")
        if wait_for:
            await page.wait_for_selector(wait_for, timeout=90_000)
    elif action_type == "script":
        if action.get("expects_navigation", "true") == "true":
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=60_000):
                await page.evaluate(f"() => {{ {data} }}")
        else:
            await page.evaluate(f"() => {{ {data} }}")
        await page.wait_for_load_state("domcontentloaded", timeout=60_000)
    else:
        raise ValueError(f"Unknown action type: {action_type}")

    save_html(out_dir, step, await page_content(page))
    if await check_captcha(page, check_captcha_expr, site_name):
        await wait_captcha_solved(page, check_captcha_expr)


async def run_site_parser(
    context,
    *,
    site_name: str,
    actions: list[dict[str, str]],
    parse_html: Callable[[str], list[SearchResult]],
    check_captcha_expr: str,
    headless_env: str,
    enrich_characteristics: Callable | None = None,
    locale: str = "ru-RU",
    block_images: bool = True,
) -> list[SearchResult]:
    _, out_dir = site_paths(site_name)
    headless = headless_from_env(headless_env)

    page = await context.new_page()
    if not headless:
        logger.info("Browser running headful — captcha can be solved manually")

    if block_images:
        await page.route(
            re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|ico)(\?|$)", re.I),
            lambda route: route.abort(),
        )

    for step, action in enumerate(actions, start=1):
        logger.info("Action %d/%d: %s", step, len(actions), action["type"])
        await run_action(
            page,
            action,
            step,
            out_dir=out_dir,
            check_captcha_expr=check_captcha_expr,
            site_name=site_name,
        )

    html = await page_content(page)
    save_html(out_dir, len(actions) + 1, html)
    products = parse_html(html)
    logger.info("Parsed %d products from %s", len(products), site_name)
    if enrich_characteristics is not None:
        await enrich_characteristics(page, products)
    return products


def extract_name(obj: dict) -> str | None:
    for key in ("raw", "text", "title", "name", "full", "short", "productTitle"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    titles = obj.get("titles")
    if isinstance(titles, dict):
        return extract_name(titles)
    main_state = obj.get("mainState")
    if isinstance(main_state, list):
        for block in main_state:
            if isinstance(block, dict) and block.get("type") == "textAtom":
                text = block.get("textAtom", {}).get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return None


def extract_price(obj: dict) -> str | None:
    for key in ("price", "value", "currentPrice", "min", "amount", "finalPrice", "salePrice"):
        val = obj.get(key)
        if isinstance(val, (int, float)):
            return _format_price(val)
        if isinstance(val, str) and val.strip():
            return val.strip()
    for key in ("salePriceU", "priceU"):
        val = obj.get(key)
        if isinstance(val, int):
            return str(val // 100)
    prices = obj.get("prices")
    if isinstance(prices, dict):
        for sub in prices.values():
            if isinstance(sub, dict):
                found = extract_price(sub)
                if found:
                    return found
    price_block = obj.get("priceV2") or obj.get("priceObject")
    if isinstance(price_block, dict):
        return extract_price(price_block)
    return None


def _format_price(val: int | float) -> str:
    return str(int(val)) if float(val).is_integer() else str(val)


def extract_image(obj: dict) -> str | None:
    for key in ("url", "src", "original", "image", "picture", "imageUrl"):
        val = obj.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    for key in ("pictures", "images", "thumbnails", "avatars", "pics"):
        items = obj.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and item.startswith("http"):
                    return item
                if isinstance(item, dict):
                    found = extract_image(item)
                    if found:
                        return found
        if isinstance(items, dict):
            for item in items.values():
                if isinstance(item, dict):
                    found = extract_image(item)
                    if found:
                        return found
    return None


def append_characteristic(
    specs: dict[str, str],
    name: str,
    value: object | None,
) -> None:
    if value is None:
        return
    key = str(name).strip()
    val = str(value).strip()
    if not key or not val or key in specs:
        return
    specs[key] = val


def extract_characteristics(obj: dict) -> dict[str, str]:
    specs: dict[str, str] = {}
    for key in ("specs", "fullSpecs", "filteredSpecs", "spec"):
        block = obj.get(key)
        if isinstance(block, list):
            for item in block:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("title") or item.get("key")
                value = item.get("value") or item.get("text") or item.get("content")
                append_characteristic(specs, str(name), value)
        elif isinstance(block, dict):
            for k, v in block.items():
                if isinstance(v, str):
                    append_characteristic(specs, str(k), v)

    characteristics = obj.get("characteristics")
    if isinstance(characteristics, dict):
        for k, v in characteristics.items():
            append_characteristic(specs, str(k), v)
    elif isinstance(characteristics, list):
        for item in characteristics:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                append_characteristic(specs, item[0], item[1])
            elif isinstance(item, dict):
                name = item.get("name") or item.get("title") or item.get("key")
                value = item.get("value") or item.get("text") or item.get("content")
                append_characteristic(specs, str(name) if name else "", value)

    return specs


def extract_rating(obj: dict) -> str | None:
    rating = obj.get("rating")
    if isinstance(rating, dict):
        value = rating.get("rating") or rating.get("value")
        if value is not None:
            return str(value)
        return None
    if isinstance(rating, (int, float, str)) and str(rating).strip():
        return str(rating)
    review_rating = obj.get("reviewRating")
    if isinstance(review_rating, (int, float)):
        return str(review_rating)
    return None


def normalize_product_url(url: str, base_url: str) -> str:
    url = url.strip()
    if url.startswith("http"):
        return url
    return urljoin(base_url, url)


def extract_product_link(obj: dict, *, base_url: str | None = None) -> str | None:
    action = obj.get("action")
    if isinstance(action, dict):
        link = action.get("link")
        if isinstance(link, str) and link.strip():
            return normalize_product_url(link, base_url) if base_url else link

    for key in ("productUrl", "product_link", "canonicalUrl", "href"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            if val.startswith("http"):
                return val
            if base_url and val.startswith("/"):
                return urljoin(base_url, val)

    for key in ("url", "link"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            if val.startswith("http"):
                return val
            if base_url and val.startswith("/"):
                return urljoin(base_url, val)

    nm_id = obj.get("id") or obj.get("nmId")
    if nm_id is not None and str(nm_id).isdigit():
        return f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"

    return None


def extract_reviews(obj: dict) -> str | None:
    rating = obj.get("rating")
    if isinstance(rating, dict):
        count = rating.get("gradesCount") or rating.get("reviews") or rating.get("count")
        if count is not None:
            return str(count)
    for key in ("feedbacks", "gradesCount", "reviews", "reviewCount", "reviewsCount"):
        value = obj.get(key)
        if value is not None:
            return str(value)
    return None


def product_from_dict(obj: dict) -> SearchResult | None:
    name = extract_name(obj)
    if not name:
        return None
    return SearchResult(
        name=name,
        characteristics=extract_characteristics(obj),
        product_link=extract_product_link(obj),
        price=extract_price(obj),
        image_link=extract_image(obj),
        rating=extract_rating(obj),
        reviews=extract_reviews(obj),
    )


def collect_products(
    node: object,
    seen: set[int],
    out: list[SearchResult],
    *,
    product_keys: tuple[str, ...],
) -> None:
    if isinstance(node, dict):
        oid = id(node)
        if oid in seen:
            return
        seen.add(oid)
        if any(k in node for k in product_keys):
            append_product(out, product_from_dict(node))
        for value in node.values():
            collect_products(value, seen, out, product_keys=product_keys)
    elif isinstance(node, list):
        for item in node:
            collect_products(item, seen, out, product_keys=product_keys)


def parse_api_payload(
    raw: str,
    *,
    product_keys: tuple[str, ...],
    empty_values: frozenset[str] = frozenset({"", "no data", "not found"}),
) -> list[SearchResult]:
    if raw.strip() in empty_values:
        return []
    if raw.startswith("error:"):
        logger.warning("API returned error: %s", raw[:200])
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Result is not valid JSON")
        return []

    products: list[SearchResult] = []
    collect_products(data, set(), products, product_keys=product_keys)
    return products


def parse_result_pre(
    html: str,
    *,
    product_keys: tuple[str, ...],
    fallback: Callable[[str], list[SearchResult]] | None = None,
) -> list[SearchResult]:
    raw = extract_pre_content(html)
    if raw is not None:
        products = parse_api_payload(raw, product_keys=product_keys)
        if products:
            return products
    if fallback:
        return fallback(html)
    return []
