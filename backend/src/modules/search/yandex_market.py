"""Yandex Market search parser using cloakbrowser."""

import html as html_module
import json
import re
from urllib.parse import quote_plus, urljoin

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
    extract_pre_content,
    normalize_display_text,
    normalize_product_url,
    page_content,
    parse_api_payload,
    run_site_parser,
)
from .details import enrich_product_characteristics, specs_from_raw
from .region_geo import get_city_geo, make_yandex_setup_page, yandex_sync_region_ui_script
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

async function waitForCorrectedQuery(originalSearchText) {
  let resolved = resolveSearchText(originalSearchText);
  if (normalizeQuery(resolved) !== normalizeQuery(originalSearchText)) {
    return resolved;
  }
  for (let attempt = 0; attempt < 8; attempt++) {
    if (extractDomProducts().length > 0) {
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

function writeDomPayloadIfReady(originalSearchText, searchText) {
  const domProducts = extractDomProducts();
  if (domProducts.length === 0) {
    return false;
  }
  writePayload(
    originalSearchText,
    searchText,
    JSON.stringify({__domProducts: domProducts})
  );
  return true;
}

function splitProductSnippetParts(html) {
  const plain = html.split('data-zone-name="productSnippet"');
  if (plain.length > 1) {
    return plain.slice(1);
  }
  return html.split('data-zone-name=\\"productSnippet\\"').slice(1);
}

function extractDomProducts() {
  const products = [];
  const parts = splitProductSnippetParts(document.documentElement.innerHTML);
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    const titleMatch =
      part.match(/data-auto="snippet-title"[^>]*title="([^"]+)"/) ||
      part.match(/data-auto=\\"snippet-title\\"[^>]*title=\\"([^"\\]+)\\"/);
    const linkMatch =
      part.match(/href="(\/card\/[^"?]+)/) ||
      part.match(/href=\\"(\/card\/[^"?\\]+)/);
    if (!linkMatch) {
      continue;
    }
    let price = null;
    const priceMatch = part.match(
      /data-auto="snippet-price-current"[^>]*>[\\s\\S]*?([\\d\\s\\u00a0\\u2009]+)\\s*₽/
    );
    if (priceMatch) {
      price = priceMatch[1].replace(/\\s/g, "").replace(/\\u00a0/g, "").replace(/\\u2009/g, "");
    }
    products.push({
      name: titleMatch ? titleMatch[1] : "Product",
      price: price,
      product_link: "https://market.yandex.ru" + linkMatch[1],
    });
  }
  return products;
}

function writePayload(originalSearchText, searchText, payload) {
  document.body = document.createElement("body");
  if (normalizeQuery(searchText) !== normalizeQuery(originalSearchText)) {
    const typoPre = document.createElement("pre");
    typoPre.id = "__TYPOFIX_PRE_ID__";
    typoPre.innerText = searchText;
    document.body.append(typoPre);
  }
  const resultPre = document.createElement("pre");
  resultPre.id = "__PRE_ID__";
  resultPre.innerText = payload;
  document.body.append(resultPre);
}

async function fetchWithRetry() {
  const delays = [300, 600, 1200, 2000];
  const originalSearchText = __SEARCH_TEXT__;

  await waitForUrlStable();
  const searchText = await waitForCorrectedQuery(originalSearchText);

  const resetBtn = document.querySelector('[data-auto="reset-filters"]');
  if (resetBtn) {
    resetBtn.click();
    for (let attempt = 0; attempt < 6; attempt++) {
      await delay(300);
      if (writeDomPayloadIfReady(originalSearchText, searchText)) {
        return true;
      }
    }
  }

  if (writeDomPayloadIfReady(originalSearchText, searchText)) {
    return true;
  }

  for (let attempt = 0; attempt < 8; attempt++) {
    if (
      document.querySelector('[data-apiary-widget-name="@search/Url"] noframes') ||
      document.querySelectorAll('[data-zone-name="productSnippet"]').length > 0
    ) {
      break;
    }
    await delay(300);
  }

  if (writeDomPayloadIfReady(originalSearchText, searchText)) {
    return true;
  }

  for (let attempt = 0; attempt <= delays.length; attempt++) {
    try {
      const noframes = document.querySelector('[data-apiary-widget-name="@search/Url"] noframes');
      if (!noframes) {
        if (writeDomPayloadIfReady(originalSearchText, searchText)) {
          return true;
        }
        if (attempt < delays.length) {
          await delay(delays[attempt]);
          continue;
        }
        writePayload(originalSearchText, searchText, "no data");
        return true;
      }

      const state = JSON.parse(noframes.textContent);
      const pageToken = state.collections.backendState
        ? state.collections.backendState["page-token"]
        : null;
      const inState = state.collections.backendState
        ? state.collections.backendState["internal-state"]
        : null;

      function extractMarketFrontGlueFromHTML(html) {
        const match = html.match(/"marketFrontGlue"\\s*:\\s*"([^"]+)"/);
        return match ? match[1] : null;
      }

      function extractUserSkFromHTML(html) {
        const match = html.match(/"sk"\\s*:\\s*"([^"]+)"/);
        return match ? match[1] : null;
      }

      function extractVersionFromHTML(html) {
        const match = html.match(/"version"\\s*:\\s*"([^"]+)"/);
        return match ? match[1] : null;
      }

      const htmlString = document.head.innerHTML;
      const glue = extractMarketFrontGlueFromHTML(htmlString);
      const sk = extractUserSkFromHTML(htmlString);
      const version = extractVersionFromHTML(htmlString);
      const url_string = document.location.href;
      const url = new URL(url_string);
      const rs = url.searchParams.get("rs") || "";

      const body = JSON.stringify({
        params: [{
          text: searchText,
          how: "dpop",
          searchPlace: "__standalone__",
          page: 1,
          withResults: true,
          rs: rs,
          isLocalOffersFirst: false,
          noSearchResults: false,
          omitFilters: false,
          viewtype: "list",
          prevTotal: 166,
          isDeliveryFilterChange: false,
          searchPlaceAction: "filter",
          urlParams: {},
          filters: filterObj,
          backendState: {
            "internal-state": inState || "",
            "page-token": pageToken || "",
            rs: rs,
            madv_state: ""
          }
        }],
        path: document.location.pathname + document.location.search
      });

      const response = await fetch(
        "https://market.yandex.ru/api/resolve/?r=src/resolvers/search/resolvePoorRemoteSearch:resolvePoorRemoteSearch",
        {
          headers: {
            accept: "*/*",
            "accept-language": "ru-RU,ru;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json",
            pragma: "no-cache",
            priority: "u=1, i",
            "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Google Chrome\";v=\"138\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            cookie: document.cookie,
            sk: sk,
            "x-market-app-version": version,
            "x-market-core-service": "<UNKNOWN>",
            "x-market-front-glue": glue,
            "x-market-page-id": "market:search",
            "x-requested-with": "XMLHttpRequest",
            "x-retpath-y": url_string
          },
          body: body,
          method: "POST",
          mode: "cors",
          credentials: "include"
        }
      );
      const data = await response.text();
      if (data && data.length > 100) {
        writePayload(originalSearchText, searchText, data);
        return true;
      }

      if (writeDomPayloadIfReady(originalSearchText, searchText)) {
        return true;
      }

      if (attempt < delays.length) {
        await delay(delays[attempt]);
      }
    } catch (error) {
      if (writeDomPayloadIfReady(originalSearchText, searchText)) {
        return true;
      }
      if (attempt < delays.length) {
        await delay(delays[attempt]);
      }
    }
  }

  if (writeDomPayloadIfReady(originalSearchText, searchText)) {
    return true;
  }

  writePayload(originalSearchText, searchText, "no data");
  return true;
}

return await fetchWithRetry();"""

_PRODUCT_KEYS = ("titles", "prices", "pictures", "productName", "slug", "skuId", "modelName")
_YANDEX_BASE_URL = "https://market.yandex.ru"
_CARD_PATH_RE = re.compile(r"/card/[a-z0-9][a-z0-9-]*/\d+")
_PRODUCT_SNIPPET_RE = re.compile(
    r'data-zone-name=\\"productSnippet\\" data-zone-data=\\"(\{.*?)\\"',
    re.DOTALL,
)


def _extract_yandex_card_links(source: object) -> dict[str, str]:
    text = source if isinstance(source, str) else json.dumps(source, ensure_ascii=False)
    links: dict[str, str] = {}
    for path in _CARD_PATH_RE.findall(text):
        product_id = path.rsplit("/", 1)[-1]
        links[product_id] = urljoin(_YANDEX_BASE_URL, path)
    return links


def _yandex_product_link(zone: dict, card_links: dict[str, str]) -> str | None:
    for key in ("url", "link", "productUrl"):
        val = zone.get(key)
        if isinstance(val, str) and val.strip():
            return normalize_product_url(val, _YANDEX_BASE_URL)

    for id_key in ("oskuId", "marketSku", "skuId", "modelId"):
        val = zone.get(id_key)
        if val is not None:
            link = card_links.get(str(val))
            if link:
                return link
    return None


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
        .replace("__PRE_ID__", RESULT_PRE_ID)
        .replace("__TYPOFIX_PRE_ID__", TYPOFIX_PRE_ID)
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


def _decode_embedded_zone_json(raw: str) -> dict:
    decoded = html_module.unescape(html_module.unescape(raw))
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        # Titles like 16" leave invalid \" after HTML unescape (16\\").
        repaired = re.sub(r'(\d+(?:\.\d+)?)\\+"', r'\1\\"', decoded)
        return json.loads(repaired)


def _price_from_snippet(zone: dict) -> str | None:
    for entry in zone.get("additionalPrices") or []:
        if isinstance(entry, dict) and entry.get("priceType") == "yaBank":
            value = entry.get("priceValue")
            if value is not None:
                return str(value)
    price = zone.get("price")
    if price is not None:
        return str(price)
    children = zone.get("children")
    if isinstance(children, dict):
        price_block = children.get("price") or children.get("wishlist", {}).get("price")
        if isinstance(price_block, dict):
            value = price_block.get("value")
            if value is not None:
                return str(value)
    return None


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
    specs = specs_from_raw(await page.evaluate(_YANDEX_DETAIL_SPECS_JS))
    if specs:
        return specs
    return parse_yandex_detail_html(await page_content(page))


async def _enrich_yandex_characteristics(page, products: list[SearchResult]) -> None:
    await enrich_product_characteristics(
        page,
        products,
        fetch_characteristics=fetch_yandex_detail_characteristics,
        check_captcha_expr=CHECK_CAPTCHA,
        site_name=SITE,
    )


def _product_from_snippet(zone: dict, card_links: dict[str, str]) -> SearchResult | None:
    name = zone.get("title")
    children = zone.get("children")
    wishlist = children.get("wishlist", {}) if isinstance(children, dict) else {}
    if not name and isinstance(wishlist, dict):
        name = wishlist.get("title")
    if not name or not str(name).strip():
        return None

    image = wishlist.get("picture") if isinstance(wishlist, dict) else None
    if not isinstance(image, str) or not image.startswith("http"):
        image = None

    rating_block = zone.get("rating")
    rating_value: str | None = None
    reviews_value: str | None = None
    if isinstance(rating_block, dict):
        if rating_block.get("rating") is not None:
            rating_value = str(rating_block["rating"])
        if rating_block.get("gradesCount") is not None:
            reviews_value = str(rating_block["gradesCount"])

    return SearchResult(
        name=normalize_display_text(str(name)),
        product_link=_yandex_product_link(zone, card_links),
        price=_price_from_snippet(zone),
        image_link=image,
        rating=rating_value,
        reviews=reviews_value,
    )


def _attach_card_links(products: list[SearchResult], card_links: dict[str, str]) -> None:
    if not card_links:
        return
    for product in products:
        if product.product_link:
            continue
        for token in re.findall(r"\d{6,}", product.name):
            link = card_links.get(token)
            if link:
                product.product_link = link
                break


def _split_product_snippet_parts(html: str) -> list[str]:
    parts = html.split('data-zone-name="productSnippet"')
    if len(parts) > 1:
        return parts[1:]
    return re.split(
        r'data-zone-name=\\"productSnippet\\"',
        html,
        flags=re.IGNORECASE,
    )[1:]


def _collect_products_from_dom_html(html: str) -> list[SearchResult]:
    products: list[SearchResult] = []
    for part in _split_product_snippet_parts(html):
        title_match = re.search(
            r'data-auto="snippet-title"[^>]*title="([^"]+)"',
            part,
        ) or re.search(
            r'data-auto=\\"snippet-title\\"[^>]*title=\\"([^"\\]+)\\"',
            part,
        )
        link_match = re.search(r'href="(/card/[^"?]+)', part) or re.search(
            r'href=\\"(/card/[^"?\\]+)',
            part,
        )
        if not link_match:
            continue
        price_match = re.search(
            r'data-auto="snippet-price-current"[^>]*>[\s\S]*?([\d\s\u00a0\u2009]+)\s*₽',
            part,
        )
        price = re.sub(r"\s+", "", price_match.group(1)) if price_match else None
        name = title_match.group(1) if title_match else "Product"
        append_product(
            products,
            SearchResult(
                name=name,
                product_link=normalize_product_url(link_match.group(1), _YANDEX_BASE_URL),
                price=price,
            ),
        )
    return products


def _parse_dom_products_payload(raw: str) -> list[SearchResult]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("__domProducts")
    if not isinstance(items, list):
        return []
    products: list[SearchResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        link = item.get("product_link")
        append_product(
            products,
            SearchResult(
                name=name.strip(),
                product_link=normalize_product_url(str(link), _YANDEX_BASE_URL) if link else None,
                price=str(item["price"]) if item.get("price") is not None else None,
            ),
        )
    return products


def _collect_products_from_snippets(
    html: str,
    card_links: dict[str, str],
) -> list[SearchResult]:
    products: list[SearchResult] = []
    for raw in _PRODUCT_SNIPPET_RE.findall(html):
        try:
            zone = _decode_embedded_zone_json(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if zone.get("snippet_type") != "product" and zone.get("type") != "offer":
            continue
        append_product(products, _product_from_snippet(zone, card_links))
    return products


def _collect_products_from_legacy_html(html: str) -> list[SearchResult]:
    products: list[SearchResult] = []
    for block in re.finditer(r'"titles"\s*:\s*\{[^}]*"raw"\s*:\s*"([^"]+)"', html):
        name = block.group(1).encode().decode("unicode_escape")
        price_match = re.search(
            r'"price"\s*:\s*\{[^}]*"value"\s*:\s*"?(\d+)"?',
            html[block.start() : block.start() + 4000],
        )
        img_match = re.search(
            r'"url"\s*:\s*"(https?://[^"]+)"',
            html[block.start() : block.start() + 4000],
        )
        append_product(
            products,
            SearchResult(
                name=name,
                characteristics={},
                price=price_match.group(1) if price_match else None,
                image_link=img_match.group(1) if img_match else None,
            ),
        )
    return products


def parse_html(html: str) -> list[SearchResult]:
    card_links = _extract_yandex_card_links(html)
    raw = extract_pre_content(html)
    if raw and raw != "no data":
        if raw.startswith("{") and "__domProducts" in raw:
            dom_products = _parse_dom_products_payload(raw)
            if dom_products:
                return dom_products

        try:
            card_links = {**card_links, **_extract_yandex_card_links(json.loads(raw))}
        except json.JSONDecodeError:
            pass

        products = parse_api_payload(raw, product_keys=_PRODUCT_KEYS)
        if products:
            _attach_card_links(products, card_links)
            return products

    dom_html = _collect_products_from_dom_html(html)
    if dom_html:
        return dom_html

    snippets = _collect_products_from_snippets(html, card_links)
    if snippets:
        return snippets

    return _collect_products_from_legacy_html(html)


async def run_yandex_market_parser(
    context,
    user_input: str,
    *,
    region: str | None = None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> tuple[SearchSource, str | None]:
    """Run Yandex Market search and return parsed products."""
    geo = get_city_geo(region)

    async def run_for_query(query: str):
        return await run_site_parser(
            context,
            site_name=SITE,
            actions=_build_actions(query, geo=geo, min_price=min_price, max_price=max_price),
            parse_html=parse_html,
            parse_typofix=lambda html: parse_yandex_market_typofix(html, original=user_input),
            original_query=user_input,
            check_captcha_expr=CHECK_CAPTCHA,
            headless_env=HEADLESS_ENV,
            enrich_characteristics=_enrich_yandex_characteristics,
            setup_page=make_yandex_setup_page(geo) if geo else None,
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
