"""Wildberries search parser using cloakbrowser."""

import json
from urllib.parse import quote

from src.modules.search.schemas import SearchSource

from .common import (
    DEFAULT_MAX_PRICE,
    DEFAULT_MIN_PRICE,
    RESULT_PRE_ID,
    SearchResult,
    append_product,
    build_price_filter,
    encode_query,
    extract_pre_content,
    parse_api_payload,
    parse_result_pre,
    run_site_parser,
)

SITE = "wildberries"
CHECK_CAPTCHA = "document.querySelector('#wait_msg') != null || document.querySelector('.support-title') != null"
HEADLESS_ENV = "WILDBERRIES_HEADLESS"
DEST = "-1198055"

_WAIT_QUERY_ID = r"""function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

async function waitForElement(timeout = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    let queryId = sessionStorage.query_id_search != null && sessionStorage.query_id_search != '';
    let powToken = localStorage.getItem('session-pow-token') != null && localStorage.getItem('session-pow-token') != '';
    let wbaas = getCookie('x_wbaas_token');
    if (queryId && wbaas != undefined && wbaas != '') {
      let g = document.createElement('pre');
      g.setAttribute("id", "queryId");
      g.innerText = sessionStorage.query_id_search;
      document.body.append(g);
      if (powToken) {
        let g2 = document.createElement('pre');
        g2.setAttribute("id", "powToken");
        g2.innerText = JSON.parse(localStorage.getItem('session-pow-token')).token;
        document.body.append(g2);
      }
      return true;
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  return false;
}

return await waitForElement();"""

_WAIT_FETCH_TEMPLATE = r"""let notFound = document.querySelector('.content404') != null
    || (document.querySelector('.searching-results__count') != null && document.querySelector('.searching-results__count').textContent == '0 товаров найдено')
    || (document.querySelector('.not-found-search__title') != null);

if (notFound) {
    document.body = document.createElement("body");
    let g = document.createElement('pre');
    g.setAttribute("id", "__PRE_ID__");
    g.innerHTML = 'not found';
    document.body.append(g);
    return Promise.resolve(true);
}

var priceFilter = __PRICE_FILTER_JS__;

const queryId = document.querySelector('#queryId');
const powToken = document.querySelector('#powToken') ? document.querySelector('#powToken').textContent : null;
const apiUrl = "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search?ab_testing=false&appType=1&curr=rub&dest=__DEST__&hide_dtype=11&inheritFilters=false&lang=ru&page=1" + priceFilter + "&query=__QUERY_ENC__&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false";
const referrer = "https://www.wildberries.ru/catalog/0/search.aspx?search=__QUERY_ENC__";

let headers;
if (queryId && queryId.textContent != '' && powToken) {
  headers = {"x-pow": powToken, "x-queryid": queryId.textContent, "cookie": document.cookie};
} else {
  headers = {
    "x-requested-with": "XMLHttpRequest",
    "x-spa-version": "13.14.1",
    "x-userid": "0",
    "x-queryid": queryId ? queryId.textContent : null,
    "cookie": document.cookie
  };
}

return fetch(apiUrl, {"headers": headers, "referrer": referrer, "method": "GET", "mode": "cors", "credentials": "include"})
  .then(response => response.text())
  .then(data => {
    let g = document.createElement('pre');
    g.setAttribute("id", "__PRE_ID__");
    g.innerText = data;
    document.body.append(g);
    return true;
  })
  .catch(error => {
    document.body = document.createElement('body');
    let g = document.createElement('pre');
    g.setAttribute("id", "__PRE_ID__");
    g.innerText = 'error: ' + error;
    document.body.append(g);
    return true;
  });"""

_PRODUCT_KEYS = ("name", "salePriceU", "priceU", "brand", "id", "pics")


def _wb_price_filter_js(
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> str:
    if min_price <= 0 and max_price >= DEFAULT_MAX_PRICE:
        return "''"
    return json.dumps(build_price_filter("&priceU=[minPrice];[maxPrice]", min_price=min_price, max_price=max_price))


def _build_actions(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> list[dict[str, str]]:
    encoded = encode_query(query)
    search_url = f"https://www.wildberries.ru/catalog/0/search.aspx?page=1&search={encoded}"
    fetch_script = (
        _WAIT_FETCH_TEMPLATE.replace("__PRE_ID__", RESULT_PRE_ID)
        .replace("__DEST__", DEST)
        .replace("__QUERY_ENC__", quote(query))
        .replace("__PRICE_FILTER_JS__", _wb_price_filter_js(min_price, max_price))
    )
    return [
        {"type": "url", "data": search_url},
        {"type": "wait", "data": "5000"},
        {"type": "waitElement", "data": _WAIT_QUERY_ID, "wait_for": "pre#queryId"},
        {"type": "wait", "data": "5000"},
        {"type": "waitElement", "data": fetch_script},
    ]


def _wb_image_url(product: dict) -> str | None:
    nm_id = product.get("id") or product.get("nmId")
    pics = product.get("pics")
    if not nm_id:
        return None
    vol = int(nm_id) // 100000
    part = int(nm_id) // 1000
    pic_idx = 1
    if isinstance(pics, int) and pics > 0:
        pic_idx = 1
    basket = product.get("wh") or 1
    return f"https://basket-{basket:02d}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/big/{pic_idx}.webp"


def _product_from_wb(item: dict) -> SearchResult | None:
    name = item.get("name")
    if not name:
        return None
    brand = item.get("brand")
    if brand:
        name = f"{brand} {name}".strip()

    price = item.get("salePriceU") or item.get("priceU")
    price_str = str(price // 100) if isinstance(price, int) else None

    characteristics: dict[str, str] = {}
    if item.get("rating"):
        characteristics["rating"] = str(item["rating"])
    if item.get("feedbacks"):
        characteristics["feedbacks"] = str(item["feedbacks"])

    return SearchResult(
        name=str(name).strip(),
        characteristics=characteristics,
        price=price_str,
        image_link=_wb_image_url(item),
    )


def _parse_wb_payload(data: object) -> list[SearchResult]:
    products: list[SearchResult] = []
    if not isinstance(data, dict):
        return products

    items = data.get("products")
    if items is None and isinstance(data.get("data"), dict):
        items = data["data"].get("products")

    if not isinstance(items, list):
        return products

    for item in items:
        if isinstance(item, dict):
            append_product(products, _product_from_wb(item))
    return products


def parse_html(html: str) -> list[SearchResult]:
    raw = extract_pre_content(html)
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            wb_products = _parse_wb_payload(data)
            if wb_products:
                return wb_products
        products = parse_api_payload(raw, product_keys=_PRODUCT_KEYS)
        if products:
            return products
    return parse_result_pre(html, product_keys=_PRODUCT_KEYS)


def run_wildberries_parser(
    user_input: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> SearchSource:
    """Run Wildberries search and return parsed products."""
    results = run_site_parser(
        site_name=SITE,
        actions=_build_actions(user_input, min_price=min_price, max_price=max_price),
        parse_html=parse_html,
        check_captcha=CHECK_CAPTCHA,
        headless_env=HEADLESS_ENV,
    )
    return SearchSource(
        source_type="wildberries",
        source_url="https://wildberries.ru",
        source_title="Wildberries",
        source_favicon_url=None,
        results=results,
    )


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "tasty coffee в зернах"
    results = run_wildberries_parser(query)
    print(results.model_dump_json(ensure_ascii=False))
