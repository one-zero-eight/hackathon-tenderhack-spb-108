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
    SearchResult,
    append_product,
    build_price_filter,
    extract_pre_content,
    normalize_product_url,
    parse_api_payload,
    run_site_parser,
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
CITY_LR = "2"

_WAIT_ELEMENT_TEMPLATE = r"""var filters = "{\"resale_goods\":\"resale_new\"";

if ('__MIN_PRICE__' != '0') {
    filters += ",\"pricefrom\":\"__MIN_PRICE__\"";
}

if ('__MAX_PRICE__' != '9999999' && '__MIN_PRICE__' != '__MAX_PRICE__') {
    filters += ",\"priceto\":\"__MAX_PRICE__\"";
}
filters += "}";

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchWithRetry() {
  const delays = [1000, 2000, 4000, 6000, 7000];
  const searchText = __SEARCH_TEXT__;

  for (let attempt = 0; attempt <= delays.length; attempt++) {
    try {
      let noframes = document.querySelector('[data-apiary-widget-name="@search/Url"] noframes');

      if (noframes == null) {
        if (attempt < delays.length) {
            await delay(delays[attempt]);
        } else {
            document.body = document.createElement("body");
          let g = document.createElement('pre');
          g.setAttribute("id", "__PRE_ID__");
          g.innerText = 'no data';
          document.body.append(g);
            return Promise.resolve(true);
       }
     }

let state = JSON.parse(noframes.textContent);

let pageToken = state.collections.backendState ? state.collections.backendState["page-token"] : null;
let inState = state.collections.backendState ? state.collections.backendState["internal-state"] : null;

function extractMarketFrontGlueFromHTML(html) {
  const match = html.match(/"marketFrontGlue"\s*:\s*"([^"]+)"/);
  return match ? match[1] : null;
}

function extractUserSkFromHTML(html) {
  const match = html.match(/"sk"\s*:\s*"([^"]+)"/);
  return match ? match[1] : null;
}

function extractVersionFromHTML(html) {
  const match = html.match(/"version"\s*:\s*"([^"]+)"/);
  return match ? match[1] : null;
}

const htmlString = document.head.innerHTML;
const glue = extractMarketFrontGlueFromHTML(htmlString);
const sk = extractUserSkFromHTML(htmlString);
const version = extractVersionFromHTML(htmlString);

var url_string = document.location.href;
var url = new URL(url_string);
var rs = url.searchParams.get("rs");

let body = "{\"params\":[{\"text\":\"" + searchText + "\",\"how\":\"dpop\",\"searchPlace\":\"__standalone__\",\"page\":1,\"withResults\":true,\"rs\":\"" + (rs || "") + "\",\"isLocalOffersFirst\":false,\"noSearchResults\":false,\"omitFilters\":false,\"viewtype\":\"list\",\"prevTotal\":166,\"isDeliveryFilterChange\":false,\"searchPlaceAction\":\"filter\",\"urlParams\":{},\"filters\":" + filters + ",\"backendState\":{\"internal-state\":\"" + (inState || "") + "\",\"page-token\":\"" + (pageToken || "") + "\",\"rs\":\"" + (rs || "") + "\",\"madv_state\":\"\"}}],\"path\":\"" + document.location.pathname + document.location.search + "\"}";

      const response = await fetch("https://market.yandex.ru/api/resolve/?r=src/resolvers/search/resolvePoorRemoteSearch:resolvePoorRemoteSearch", {
  "headers": {
    "accept": "*/*",
    "accept-language": "ru-RU,ru;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Google Chrome\";v=\"138\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "cookie": document.cookie,
    "sk": sk,
    "x-market-app-version": version,
    "x-market-core-service": "<UNKNOWN>",
    "x-market-front-glue": glue,
    "x-market-page-id": "market:search",
    "x-requested-with": "XMLHttpRequest",
    "x-retpath-y": url_string
  },
  "body": body,
  "method": "POST",
  "mode": "cors",
  "credentials": "include"
});
      const data = await response.text();

      if (data) {
        document.body = document.createElement("body");
  let g = document.createElement('pre');
  g.setAttribute("id", "__PRE_ID__");
        g.innerText = data;
  document.body.append(g);
        return true;
      }

      if (attempt < delays.length) {
        await delay(delays[attempt]);
      }

    } catch (error) {
      if (attempt < delays.length) {
        await delay(delays[attempt]);
      }
    }
  }

  return false;
}

return fetchWithRetry();"""

_PRODUCT_KEYS = ("titles", "prices", "pictures", "productName", "slug", "skuId", "modelName")
_YANDEX_BASE_URL = "https://market.yandex.ru"
_CARD_PATH_RE = re.compile(r"/card/[a-z0-9][a-z0-9-]*/\d+")
_PRODUCT_SNIPPET_RE = re.compile(
    r'data-zone-name=\\"productSnippet\\" data-zone-data=\\"(\{.*?\})\\"',
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
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> str:
    encoded = quote_plus(user_input)
    min_filter = build_price_filter("&pricefrom=[minPrice]", min_price=min_price, max_price=max_price)
    max_filter = build_price_filter("&priceto=[maxPrice]", min_price=min_price, max_price=max_price)
    return (
        f"https://market.yandex.ru/search?text={encoded}"
        f"&lr={CITY_LR}&resale_goods=resale_new&cvredirect=1"
        f"{min_filter}{max_filter}"
    )


def _build_actions(
    user_input: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> list[dict[str, str]]:
    search_url = _build_search_url(user_input, min_price=min_price, max_price=max_price)
    wait_script = (
        _WAIT_ELEMENT_TEMPLATE.replace("__SEARCH_TEXT__", json.dumps(user_input))
        .replace("__PRE_ID__", RESULT_PRE_ID)
        .replace("__MIN_PRICE__", str(min_price))
        .replace("__MAX_PRICE__", str(max_price))
    )
    return [
        {"type": "url", "data": "https://market.yandex.ru"},
        {"type": "wait", "data": "3000"},
        {"type": "url", "data": search_url},
        {"type": "wait", "data": "4000"},
        {"type": "waitElement", "data": wait_script},
        {"type": "wait", "data": "1000"},
    ]


def _decode_embedded_zone_json(raw: str) -> dict:
    return json.loads(html_module.unescape(html_module.unescape(raw)))


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
        name=str(name).strip(),
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
        products.append(
            SearchResult(
                name=name,
                characteristics={},
                price=price_match.group(1) if price_match else None,
                image_link=img_match.group(1) if img_match else None,
            )
        )
    return products


def parse_html(html: str) -> list[SearchResult]:
    card_links = _extract_yandex_card_links(html)
    raw = extract_pre_content(html)
    if raw is not None:
        try:
            card_links = {**card_links, **_extract_yandex_card_links(json.loads(raw))}
        except json.JSONDecodeError:
            pass
        products = parse_api_payload(raw, product_keys=_PRODUCT_KEYS)
        if products:
            _attach_card_links(products, card_links)
            return products

    snippets = _collect_products_from_snippets(html, card_links)
    if snippets:
        return snippets
    return _collect_products_from_legacy_html(html)


def run_yandex_market_parser(
    user_input: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> SearchSource:
    """Run Yandex Market search and return parsed products."""
    results = run_site_parser(
        site_name=SITE,
        actions=_build_actions(user_input, min_price=min_price, max_price=max_price),
        parse_html=parse_html,
        check_captcha=CHECK_CAPTCHA,
        headless_env=HEADLESS_ENV,
    )
    return SearchSource(
        source_type="yandex_market",
        source_url=_build_search_url(user_input, min_price=min_price, max_price=max_price),
        source_title="Яндекс Маркет",
        source_favicon_url=None,
        results=results,
    )


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "tasty coffee в зернах"
    results = run_yandex_market_parser(query)
    print(results.model_dump_json(ensure_ascii=False))
