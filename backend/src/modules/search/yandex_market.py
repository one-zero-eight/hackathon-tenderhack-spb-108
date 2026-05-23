"""Yandex Market search parser using cloakbrowser."""

import asyncio
import html as html_module
import json
import re
from urllib.parse import quote_plus

from src.logging_ import logger
from src.modules.search.schemas import SearchSource

from .common import (
    DEFAULT_MAX_PRICE,
    DEFAULT_MIN_PRICE,
    SearchResult,
    append_characteristic,
    append_product,
    build_price_filter,
    normalize_display_text,
    normalize_product_url,
    run_site_parser,
)
from .details import enrich_product_characteristics, specs_from_raw
from .region_geo import geo_for_marketplace_search, make_yandex_setup_page, yandex_sync_region_ui_script
from .typofix import parse_yandex_market_typofix, queries_differ

_YANDEX_DETAIL_SPECS_JS = """() => {
  const out = [];
  const seen = new Set();
  const add = (name, value) => {
    const key = name + '\\0' + value;
    if (!name || !value || seen.has(key)) return;
    seen.add(key);
    out.push([name, value]);
  };

  document.querySelectorAll('input[type="checkbox"][id^="group-collapse-"]').forEach((cb) => {
    if (!cb.checked) cb.click();
  });

  document.querySelectorAll('[data-auto="product-spec"]').forEach((el) => {
    const name = el.innerText.trim();
    if (!name) return;

    const row =
      el.closest('div._3rW2x') ||
      el.closest('div._2jsum') ||
      el.closest('div._7_B2r');
    if (row) {
      const valueEl =
        row.querySelector('.eXP5k span') ||
        row.querySelector('.eXP5k') ||
        row.querySelector('div._1_zPW') ||
        row.querySelector('div._19UG7') ||
        row.querySelector('[data-auto="specLink"]');
      const value = valueEl?.innerText?.trim();
      if (value) {
        add(name, value);
        return;
      }
    }

    let node = el.parentElement;
    for (let i = 0; i < 8 && node; i++) {
      if (node.querySelectorAll('[data-auto="product-spec"]').length > 1) {
        node = node.parentElement;
        continue;
      }
      const copy = node.cloneNode(true);
      copy.querySelectorAll('[data-auto="product-spec"]').forEach((s) => s.remove());
      const value = copy.innerText.replace(/\\s+/g, ' ').trim();
      if (value) {
        add(name, value);
        break;
      }
      node = node.parentElement;
    }
  });
  return out;
}"""

_YANDEX_SPEC_ROW_RE = re.compile(
    r'<span data-auto="product-spec"[^>]*>([^<]+)</span>.*?'
    r'(?:<div class="eXP5k">.*?<span>([^<]+)</span>'
    r'|<div class="_1_zPW">.*?<span>([^<]+)</span>)',
    re.DOTALL,
)

SITE = "yandex_market"
CHECK_CAPTCHA = (
    "document.location.href.indexOf('showcaptcha') != -1"
    " || document.getElementsByClassName('AdvancedCaptcha').length == 1"
    " || document.getElementsByClassName('utilityfocus').length == 1"
    " || document.getElementsByClassName('pointerfocus').length == 1"
    " || document.getElementsByClassName('CheckboxCaptcha').length == 1"
)
HEADLESS_ENV = "YANDEX_MARKET_HEADLESS"

_WAIT_ELEMENT_TEMPLATE = r"""var filterObj = {};
if ('__MIN_PRICE__' != '0') {
  filterObj.pricefrom = '__MIN_PRICE__';
}
if ('__MAX_PRICE__' != '9999999' && '__MIN_PRICE__' != '__MAX_PRICE__') {
  filterObj.priceto = '__MAX_PRICE__';
}
const filters = JSON.stringify(filterObj);

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function normalizeQuery(text) {
  return (text || '').trim().replace(/\\s+/g, ' ').toLowerCase();
}

function resolveSearchText(originalSearchText) {
  const typoInState = document.documentElement.innerHTML.match(
    /"old":"([^"\\\\]+)","new":"([^"\\\\]+)","probablyTypo":true/
  );
  if (typoInState && typoInState[2]) {
    return typoInState[2];
  }

  const searchTexts = [...document.documentElement.innerHTML.matchAll(
    /"searchText"\\s*:\\s*"([^"\\\\]+)"/g
  )].map((match) => match[1]);
  for (const candidate of searchTexts) {
    if (candidate && normalizeQuery(candidate) !== normalizeQuery(originalSearchText)) {
      return candidate;
    }
  }

  const titleMatch = document.title.match(/^(.+?)\\s+[—-]\\s+купить/i);
  if (titleMatch) {
    const fromTitle = titleMatch[1].trim();
    if (fromTitle && normalizeQuery(fromTitle) !== normalizeQuery(originalSearchText)) {
      return fromTitle;
    }
  }

  const urlText = new URL(document.location.href).searchParams.get('text');
  if (urlText) {
    const decoded = decodeURIComponent(urlText.replace(/\\+/g, ' '));
    if (decoded && normalizeQuery(decoded) !== normalizeQuery(originalSearchText)) {
      return decoded;
    }
  }
  return originalSearchText;
}

async function waitForUrlStable() {
  let lastUrl = location.href;
  let stableTicks = 0;
  for (let attempt = 0; attempt < 12; attempt++) {
    await delay(300);
    if (location.href === lastUrl) {
      stableTicks += 1;
      if (stableTicks >= 2) {
        return;
      }
    } else {
      lastUrl = location.href;
      stableTicks = 0;
    }
  }
}

function hasProductSnippets() {
  return document.querySelectorAll('[data-zone-name="productSnippet"]').length > 0;
}

async function waitForCorrectedQuery(originalSearchText) {
  let resolved = resolveSearchText(originalSearchText);
  if (normalizeQuery(resolved) !== normalizeQuery(originalSearchText)) {
    return resolved;
  }
  for (let attempt = 0; attempt < 8; attempt++) {
    if (hasProductSnippets()) {
      return resolved;
    }
    await delay(300);
    resolved = resolveSearchText(originalSearchText);
    if (normalizeQuery(resolved) !== normalizeQuery(originalSearchText)) {
      return resolved;
    }
  }
  return resolved;
}

async function fetchWithRetry() {
  const originalSearchText = __SEARCH_TEXT__;

  await waitForUrlStable();
  await waitForCorrectedQuery(originalSearchText);

  const resetBtn = document.querySelector('[data-auto="reset-filters"]');
  if (resetBtn) {
    resetBtn.click();
    for (let attempt = 0; attempt < 6; attempt++) {
      await delay(300);
      if (hasProductSnippets()) {
        return true;
      }
    }
  }

  const delays = [300, 600, 1200, 2000, 3000];
  for (const ms of delays) {
    if (hasProductSnippets()) {
      return true;
    }
    await delay(ms);
  }
  return true;
}

return await fetchWithRetry();"""

_YANDEX_BASE_URL = "https://market.yandex.ru"
_CARD_PATH_RE = re.compile(r"/card/[a-z0-9][a-z0-9-]*/\d+")
_YANDEX_COLLECT_GALLERY_MPIC_JS = """(root) => {
  const urls = [];
  const seen = new Set();
  const addImg = (img) => {
    if (!img) return;
    for (const attr of ["src", "data-src"]) {
      const src = img.getAttribute(attr);
      if (!src || !src.includes("get-mpic/") || src.includes("get-marketcms/")) continue;
      const base = src.match(
        /(https:\\/\\/avatars\\.mds\\.yandex\\.net\\/get-mpic\\/\\d+\\/[0-9a-f]+)/i
      );
      if (!base) continue;
      const key = base[1].toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      urls.push(base[1] + "/orig");
      return;
    }
  };
  const galleries =
    root?.matches?.('[data-zone-name="pictureGallery"]')
      ? [root]
      : [...(root?.querySelectorAll?.('[data-zone-name="pictureGallery"]') || [])];
  const targets = galleries.length ? galleries : root ? [root] : [];
  const selectors = [
    '[data-auto="media-viewer-gallery"] img',
    '[data-zone-name="picture"] img',
    '[data-auto="media-viewer-thumbnails"] img',
    '[data-auto="thumbnail"] img',
  ];
  for (const gallery of targets) {
    if (!gallery?.querySelectorAll) continue;
    for (const selector of selectors) {
      for (const img of gallery.querySelectorAll(selector)) {
        addImg(img);
      }
    }
  }
  return urls;
}"""


def _normalize_yandex_image_url(url: str) -> str:
    url = url.strip().rstrip('"').rstrip("'")
    if "/orig" in url:
        return url
    base = re.match(
        r"(https://avatars\.mds\.yandex\.net/get-mpic/\d+/[0-9a-f]+)",
        url,
        re.IGNORECASE,
    )
    if base:
        return base.group(1) + "/orig"
    return url


_YANDEX_MPIC_BASE_RE = re.compile(
    r"(https://avatars\.mds\.yandex\.net/get-mpic/\d+/[0-9a-f]+)",
    re.IGNORECASE,
)


def _is_yandex_product_image_url(url: str) -> bool:
    return "get-mpic/" in url.casefold() and "get-marketcms/" not in url.casefold()


def _yandex_mpic_base_key(url: str) -> str | None:
    match = _YANDEX_MPIC_BASE_RE.match(_normalize_yandex_image_url(url))
    return match.group(1).lower() if match else None


def _split_yandex_product_images(urls: list[str]) -> tuple[str | None, list[str]]:
    unique: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if not isinstance(url, str) or not url.startswith("http"):
            continue
        if not _is_yandex_product_image_url(url):
            continue
        normalized = _normalize_yandex_image_url(url)
        key = _yandex_mpic_base_key(normalized)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    if not unique:
        return None, []
    return unique[0], unique[1:]


def _merge_yandex_image_urls(product: SearchResult, urls: list[str]) -> None:
    primary, gallery = _split_yandex_product_images(
        [
            *([product.image_link] if product.image_link else []),
            *product.image_links,
            *urls,
        ]
    )
    if primary:
        product.image_link = primary
    if gallery:
        product.image_links = gallery


_SERP_LIST_SELECTOR = '[data-auto="SerpList"]'
_MAX_SERP_LIST_PAGES = 2
_ORGANIC_SNIPPET_IN_SERP = 'article[data-auto="searchOrganic"] [data-zone-name="productSnippet"]'
_SNIPPET_SELECTOR = f"{_SERP_LIST_SELECTOR} {_ORGANIC_SNIPPET_IN_SERP}"
_SPONSORED_INCUT_ZONE = "madvIncut"
_TITLE_SELECTOR = '[data-auto="snippet-title"]'
_SNIPPET_SPEC_SKIP_PREFIXES = (
    "рейтинг товара",
    "оценок:",
    "цена с",
    "по клику",
    "пвз",
    "пэй",
    "в корзину",
    "послезавтра",
    "купили",
)
_PRICE_SELECTORS = (
    '[data-auto="snippet-price-current"]',
    '[data-auto="snippet-price"]',
    '[data-auto="price-current"]',
)
_CARD_LINK_SELECTOR = 'a[href*="/card/"]'
_PICTURE_GALLERY_SELECTOR = '[data-zone-name="pictureGallery"]'
_PLACEHOLDER_NAMES = frozenset({"product", "товар"})
_SEARCH_SCROLL_BUDGET_SEC = 2.0
_SEARCH_SCROLL_STEP_PAUSE_MS = 350
_SEARCH_SCROLL_WHEEL_DELTA_Y = 700
_SEARCH_SETTLE_TIMEOUT_SEC = 3.0
_SEARCH_SETTLE_POLL_MS = 250
_SEARCH_SETTLE_STABLE_POLLS = 3
_ORGANIC_ARTICLE_SELECTOR = 'article[data-auto="searchOrganic"]'

_YANDEX_SCROLL_AND_WAIT_JS = f"""async () => {{
  const scrollBudgetMs = {int(_SEARCH_SCROLL_BUDGET_SEC * 1000)};
  const settleBudgetMs = {int(_SEARCH_SETTLE_TIMEOUT_SEC * 1000)};
  const stepPx = {_SEARCH_SCROLL_WHEEL_DELTA_Y};
  const pauseMs = {_SEARCH_SCROLL_STEP_PAUSE_MS};
  const stablePollsNeeded = {_SEARCH_SETTLE_STABLE_POLLS};
  const pollMs = {_SEARCH_SETTLE_POLL_MS};
  const maxSerpLists = {_MAX_SERP_LIST_PAGES};
  const serpListSelector = '{_SERP_LIST_SELECTOR}';
  const organicSelector = '{_ORGANIC_ARTICLE_SELECTOR}';
  const organicSnippetSelector = '{_ORGANIC_SNIPPET_IN_SERP}';

  const countSerpLists = () => document.querySelectorAll(serpListSelector).length;
  const countSnippetsInScope = () => {{
    const lists = [...document.querySelectorAll(serpListSelector)].slice(0, maxSerpLists);
    if (!lists.length) {{
      return document.querySelectorAll(organicSnippetSelector).length;
    }}
    return lists.reduce(
      (total, list) => total + list.querySelectorAll(organicSnippetSelector).length,
      0
    );
  }};

  const findScrollRoot = () => {{
    const anchors = [
      document.querySelector(organicSelector),
      document.querySelector('[data-zone-name="main"]'),
      document.querySelector('[data-zone-name="productSnippet"]'),
    ].filter(Boolean);
    for (const anchor of anchors) {{
      let el = anchor;
      while (el && el !== document.documentElement) {{
        const style = getComputedStyle(el);
        const scrollable =
          /(auto|scroll)/.test(style.overflowY) || /(auto|scroll)/.test(style.overflow);
        if (scrollable && el.scrollHeight > el.clientHeight + 80) {{
          return el;
        }}
        el = el.parentElement;
      }}
    }}
    return document.scrollingElement || document.documentElement;
  }};

  const dispatchWheel = (target, deltaY) => {{
    if (!target) return;
    const event = new WheelEvent("wheel", {{
      deltaY,
      deltaMode: 0,
      bubbles: true,
      cancelable: true,
    }});
    target.dispatchEvent(event);
  }};

  const scrollStep = () => {{
    const roots = new Set(
      [
        document.scrollingElement,
        document.documentElement,
        document.body,
        document.querySelector('[data-zone-name="main"]'),
        findScrollRoot(),
      ].filter(Boolean)
    );
    for (const root of roots) {{
      root.scrollBy(0, stepPx);
      root.dispatchEvent(new Event("scroll", {{ bubbles: true }}));
      dispatchWheel(root, stepPx);
    }}
    window.scrollBy(0, stepPx);
    window.dispatchEvent(new Event("scroll"));
    dispatchWheel(window, stepPx);
    const articles = document.querySelectorAll(organicSelector);
    const last = articles[articles.length - 1];
    if (last) {{
      last.scrollIntoView({{ block: "end", inline: "nearest", behavior: "instant" }});
    }}
  }};

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const scrollDeadline = Date.now() + scrollBudgetMs;
  while (Date.now() < scrollDeadline) {{
    scrollStep();
    if (countSerpLists() >= maxSerpLists) {{
      break;
    }}
    await sleep(Math.min(pauseMs, Math.max(0, scrollDeadline - Date.now())));
  }}

  if (countSerpLists() === 0) {{
    return countSnippetsInScope();
  }}

  let prevSnippets = countSnippetsInScope();
  let prevSerpLists = countSerpLists();
  let stablePolls = 0;
  let settleDeadline = Date.now() + settleBudgetMs;
  while (Date.now() < settleDeadline) {{
    await sleep(pollMs);
    const serpLists = countSerpLists();
    const snippets = countSnippetsInScope();
    if (snippets > prevSnippets || serpLists > prevSerpLists) {{
      prevSnippets = snippets;
      prevSerpLists = serpLists;
      stablePolls = 0;
      settleDeadline = Math.max(settleDeadline, Date.now() + pollMs * 4);
      if (serpLists < maxSerpLists) {{
        scrollStep();
      }}
      continue;
    }}
    stablePolls += 1;
    if (stablePolls >= stablePollsNeeded) {{
      break;
    }}
  }}

  return countSnippetsInScope();
}}"""


def _yandex_product_key(product_link: str | None) -> str | None:
    if not product_link:
        return None
    match = _CARD_PATH_RE.search(product_link)
    if match:
        return match.group(0).rsplit("/", 1)[-1]
    return product_link.split("?", 1)[0].rstrip("/")


def _is_placeholder_name(name: str | None) -> bool:
    if not name:
        return True
    return name.strip().casefold() in _PLACEHOLDER_NAMES


def _parse_yandex_price_text(text: str) -> str | None:
    match = re.search(r"([\d\s\u00a0\u2009\u202f]+)\s*₽", text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return digits or None


def _normalize_yandex_price(price: str | None) -> str | None:
    if price is None:
        return None
    if not isinstance(price, str):
        return str(price)
    cleaned = price.strip()
    if not cleaned:
        return None
    digits = re.sub(r"\D", "", cleaned)
    return digits or None


def _yandex_product_rank(product: SearchResult) -> tuple[int, int, int]:
    name_score = 0 if _is_placeholder_name(product.name) else len(product.name)
    price_score = 1 if product.price else 0
    image_score = 1 if product.image_link else 0
    return (name_score, price_score, image_score)


def _merge_yandex_product(dst: SearchResult, src: SearchResult) -> None:
    if _yandex_product_rank(src) > _yandex_product_rank(dst):
        if not _is_placeholder_name(src.name):
            dst.name = src.name
        if src.price:
            dst.price = src.price
    elif not _is_placeholder_name(src.name) and _is_placeholder_name(dst.name):
        dst.name = src.name
    if not dst.price and src.price:
        dst.price = src.price
    _merge_yandex_image_urls(
        dst,
        [
            *([src.image_link] if src.image_link else []),
            *(src.image_links or []),
        ],
    )
    if not dst.rating and src.rating:
        dst.rating = src.rating
    if not dst.reviews and src.reviews:
        dst.reviews = src.reviews
    for name, value in src.characteristics.items():
        if name not in dst.characteristics:
            dst.characteristics[name] = value


def _dedupe_yandex_products(products: list[SearchResult]) -> list[SearchResult]:
    by_key: dict[str, SearchResult] = {}
    orphans: list[SearchResult] = []
    for product in products:
        product.price = _normalize_yandex_price(product.price)
        key = _yandex_product_key(product.product_link)
        if not key:
            append_product(orphans, product)
            continue
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = product
            continue
        _merge_yandex_product(existing, product)
    merged = list(by_key.values()) + orphans
    return sorted(merged, key=_yandex_product_rank, reverse=True)


async def _read_snippet_title(snippet) -> str | None:
    title = snippet.locator(_TITLE_SELECTOR).first
    if await title.count() > 0:
        for value in (
            await title.get_attribute("title"),
            await title.inner_text(),
        ):
            if isinstance(value, str) and value.strip():
                return normalize_display_text(html_module.unescape(value.strip()))

    link = snippet.locator(_CARD_LINK_SELECTOR).first
    if await link.count() > 0:
        for attr in ("aria-label", "title"):
            value = await link.get_attribute(attr)
            if isinstance(value, str) and value.strip():
                return normalize_display_text(html_module.unescape(value.strip()))

    for selector in ("h3", "h2", '[data-auto="snippet-title"] span'):
        node = snippet.locator(selector).first
        if await node.count() > 0:
            value = await node.inner_text()
            if isinstance(value, str) and value.strip():
                return normalize_display_text(html_module.unescape(value.strip()))
    return None


def _parse_snippet_spec_lines(text: str) -> dict[str, str]:
    specs: dict[str, str] = {}
    for line in text.splitlines():
        normalized = normalize_display_text(html_module.unescape(line.strip()))
        if not normalized or ":" not in normalized:
            continue
        lowered = normalized.casefold()
        if "₽" in normalized or any(lowered.startswith(prefix) for prefix in _SNIPPET_SPEC_SKIP_PREFIXES):
            continue
        name, _, value = normalized.partition(":")
        name = name.strip()
        value = value.strip()
        if name and value:
            append_characteristic(specs, name, value)
    return specs


async def _read_snippet_characteristics(snippet) -> dict[str, str]:
    text = await snippet.inner_text()
    return _parse_snippet_spec_lines(text)


async def _read_snippet_price(snippet) -> str | None:
    for selector in _PRICE_SELECTORS:
        price_el = snippet.locator(selector).first
        if await price_el.count() > 0:
            price = _parse_yandex_price_text(await price_el.inner_text())
            if price:
                return price
    return _parse_yandex_price_text(await snippet.inner_text())


async def _is_sponsored_snippet(snippet) -> bool:
    return bool(await snippet.evaluate(f"""el => !!el.closest('[data-zone-name="{_SPONSORED_INCUT_ZONE}"]')"""))


async def _read_snippet_images(snippet) -> tuple[str | None, list[str]]:
    gallery = snippet.locator(_PICTURE_GALLERY_SELECTOR).first
    if await gallery.count() == 0:
        return None, []
    evaluated = await gallery.evaluate(_YANDEX_COLLECT_GALLERY_MPIC_JS)
    if not isinstance(evaluated, list):
        return None, []
    return _split_yandex_product_images(evaluated)


async def _serp_list_count(page) -> int:
    return await page.locator(_SERP_LIST_SELECTOR).count()


async def _organic_snippet_count(page) -> int:
    serp_lists = await _serp_list_count(page)
    if serp_lists == 0:
        return await page.locator(_ORGANIC_SNIPPET_IN_SERP).count()
    take = min(serp_lists, _MAX_SERP_LIST_PAGES)
    total = 0
    for index in range(take):
        total += await page.locator(_SERP_LIST_SELECTOR).nth(index).locator(_ORGANIC_SNIPPET_IN_SERP).count()
    return total


async def _scroll_yandex_search_results(page) -> int:
    """Scroll search results in-page (JS) until organic snippets stop growing."""
    count = await page.evaluate(_YANDEX_SCROLL_AND_WAIT_JS)
    return count if isinstance(count, int) else await _organic_snippet_count(page)


def _is_sponsored_product_link(product_link: str) -> bool:
    return "sponsored=1" in product_link


async def _iter_organic_snippet_locators(page):
    serp_lists = page.locator(_SERP_LIST_SELECTOR)
    list_count = await serp_lists.count()
    if list_count == 0:
        yield page.locator(_ORGANIC_SNIPPET_IN_SERP)
        return
    for index in range(min(list_count, _MAX_SERP_LIST_PAGES)):
        yield serp_lists.nth(index).locator(_ORGANIC_SNIPPET_IN_SERP)


async def collect_products_from_page(page) -> list[SearchResult]:
    """Read search snippets from the live page via Playwright locators."""
    organic_count = await _scroll_yandex_search_results(page)
    serp_pages = await _serp_list_count(page)
    logger.info(
        "Yandex Market organic snippets ready: %d (SerpList pages: %d/%d)",
        organic_count,
        min(serp_pages, _MAX_SERP_LIST_PAGES),
        serp_pages,
    )
    by_key: dict[str, SearchResult] = {}
    async for snippets in _iter_organic_snippet_locators(page):
        count = await snippets.count()
        for index in range(count):
            snippet = snippets.nth(index)
            if await _is_sponsored_snippet(snippet):
                continue
            link = snippet.locator(_CARD_LINK_SELECTOR).first
            if await link.count() == 0:
                continue
            href = await link.get_attribute("href")
            if not href:
                continue
            product_link = normalize_product_url(href, _YANDEX_BASE_URL)
            if _is_sponsored_product_link(product_link):
                continue
            key = _yandex_product_key(product_link)
            if not key:
                continue

            name = await _read_snippet_title(snippet)
            price = await _read_snippet_price(snippet)
            image_link, image_links = await _read_snippet_images(snippet)
            characteristics = await _read_snippet_characteristics(snippet)

            if not name:
                existing = by_key.get(key)
                if existing is None:
                    continue
                if image_link or image_links:
                    incoming = SearchResult(
                        name=existing.name,
                        product_link=product_link,
                        image_link=image_link,
                        image_links=image_links,
                        characteristics=characteristics,
                    )
                    _merge_yandex_product(existing, incoming)
                continue

            incoming = SearchResult(
                name=name,
                product_link=product_link,
                price=price,
                image_link=image_link,
                image_links=image_links,
                characteristics=characteristics,
            )
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = incoming
            else:
                _merge_yandex_product(existing, incoming)

    return _dedupe_yandex_products(list(by_key.values()))


def _build_search_url(
    user_input: str,
    *,
    geo=None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> str:
    encoded = quote_plus(user_input)
    min_filter = build_price_filter("&pricefrom=[minPrice]", min_price=min_price, max_price=max_price)
    max_filter = build_price_filter("&priceto=[maxPrice]", min_price=min_price, max_price=max_price)
    lr = f"&lr={geo.yandex_lr}" if geo else ""
    return f"https://market.yandex.ru/search?text={encoded}{lr}&cvredirect=1{min_filter}{max_filter}"


def _build_actions(
    user_input: str,
    *,
    geo=None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> list[dict[str, str]]:
    search_url = _build_search_url(user_input, geo=geo, min_price=min_price, max_price=max_price)
    wait_script = (
        _WAIT_ELEMENT_TEMPLATE.replace("__SEARCH_TEXT__", json.dumps(user_input))
        .replace("__MIN_PRICE__", str(min_price))
        .replace("__MAX_PRICE__", str(max_price))
    )
    actions: list[dict[str, str]] = [
        {"type": "url", "data": search_url},
        {
            "type": "waitFor",
            "data": '[data-zone-name="productSnippet"], [data-apiary-widget-name="@search/Url"] noframes',
            "timeout": "20000",
        },
    ]
    if geo:
        actions.append(
            {
                "type": "waitElement",
                "data": yandex_sync_region_ui_script(geo),
                "wait_for": "",
            }
        )
    actions.append({"type": "waitElement", "data": wait_script, "wait_for": ""})
    return actions


def parse_yandex_detail_html(html: str) -> dict[str, str]:
    specs: dict[str, str] = {}
    for match in _YANDEX_SPEC_ROW_RE.finditer(html):
        append_characteristic(specs, match.group(1), (match.group(2) or match.group(3) or ""))
    return specs


async def fetch_yandex_detail_characteristics(page, product_link: str) -> dict[str, str]:
    await page.goto(product_link, wait_until="domcontentloaded", timeout=30_000)
    try:
        await page.wait_for_selector('[data-auto="product-spec"]', timeout=5_000)
    except Exception:
        pass
    return specs_from_raw(await page.evaluate(_YANDEX_DETAIL_SPECS_JS))


async def fetch_yandex_detail_images(page, product_link: str) -> list[str]:
    if page.url.split("?", 1)[0] != product_link.split("?", 1)[0]:
        await page.goto(product_link, wait_until="domcontentloaded", timeout=30_000)
    try:
        await page.wait_for_selector(_PICTURE_GALLERY_SELECTOR, timeout=5_000)
    except Exception:
        pass
    gallery = page.locator(_PICTURE_GALLERY_SELECTOR).first
    if await gallery.count() == 0:
        return []
    images = await gallery.evaluate(_YANDEX_COLLECT_GALLERY_MPIC_JS)
    if not isinstance(images, list):
        return []
    primary, gallery_urls = _split_yandex_product_images(images)
    return gallery_urls if gallery_urls else ([primary] if primary else [])


async def _enrich_yandex_characteristics(page, products: list[SearchResult]) -> None:
    by_link = {product.product_link: product for product in products if product.product_link}

    async def fetch_with_image(detail_page, product_link: str) -> dict[str, str]:
        detail_specs = await fetch_yandex_detail_characteristics(detail_page, product_link)
        product = by_link.get(product_link)
        if product:
            detail_images = await fetch_yandex_detail_images(detail_page, product_link)
            if detail_images:
                _merge_yandex_image_urls(product, detail_images)
            merged = dict(product.characteristics)
            merged.update(detail_specs)
            return merged
        return detail_specs

    await enrich_product_characteristics(
        page,
        products,
        fetch_characteristics=fetch_with_image,
        check_captcha_expr=CHECK_CAPTCHA,
        site_name=SITE,
    )


def parse_html(html: str) -> list[SearchResult]:
    """Parse saved search HTML the same way as the live browser (DOM snippets)."""

    from playwright.async_api import async_playwright

    async def run() -> list[SearchResult]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html, wait_until="domcontentloaded")
            try:
                return await collect_products_from_page(page)
            finally:
                await browser.close()

    return asyncio.run(run())


async def run_yandex_market_parser(
    context,
    user_input: str,
    *,
    region: str | None = None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> tuple[SearchSource, str | None]:
    """Run Yandex Market search and return parsed products."""
    geo = geo_for_marketplace_search(region)

    async def run_for_query(query: str):
        return await run_site_parser(
            context,
            site_name=SITE,
            actions=_build_actions(query, geo=geo, min_price=min_price, max_price=max_price),
            parse_html=lambda _: [],
            parse_typofix=lambda html: parse_yandex_market_typofix(html, original=user_input),
            original_query=user_input,
            check_captcha_expr=CHECK_CAPTCHA,
            headless_env=HEADLESS_ENV,
            enrich_characteristics=_enrich_yandex_characteristics,
            setup_page=make_yandex_setup_page(geo) if geo else None,
            collect_dom_products=collect_products_from_page,
            block_images=False,
        )

    results, timing, typofix = await run_for_query(user_input)

    search_query = typofix if typofix and queries_differ(user_input, typofix) else user_input
    return SearchSource(
        source_type="yandex_market",
        source_url=_build_search_url(search_query, geo=geo, min_price=min_price, max_price=max_price),
        source_title="Яндекс Маркет",
        source_favicon_url=None,
        results=results,
        timing=timing,
    ), typofix


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "tasty coffee в зернах"
    results = run_yandex_market_parser(query)
    print(results.model_dump_json(ensure_ascii=False))
