"""Ozon search parser using cloakbrowser."""

from __future__ import annotations

import json
import re
from urllib.parse import quote

from common import (
    DEFAULT_MAX_PRICE,
    DEFAULT_MIN_PRICE,
    MarketProduct,
    append_product,
    build_price_filter,
    encode_query,
    collect_products,
    extract_pre_content,
    parse_result_pre,
    product_from_dict,
    run_site_parser,
)

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
REFER = "utm_source=cheaper"
CITY_INFO = ""

_GEO_SCRIPT_TEMPLATE = r"""var cityInfoStr = __CITY_INFO__;
var cityInfo = cityInfoStr.split('/');

if (cityInfo.length == 1) {
    return Promise.resolve(true);
}

return fetch("https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url=%2Fgeo%2F" + cityInfo[0] + "%2F%3Fazimuth%3D0.000000000000%26nfr%3Dt%26pid%3D7%26pp%3D" + cityInfo[1], {
  "headers": {
    "accept": "application/json",
    "content-type": "application/json",
    "cookie": document.cookie
  },
  "body": "{\"geolocation\":{\"coords\":{},\"isAvailable\":false},\"form\":{},\"map\":{\"viewport\":{\"leftBottom\":{\"latitude\":54.70878018455491,\"longitude\":20.523989796638492},\"rightTop\":{\"latitude\":54.71124707185298,\"longitude\":20.534600615501407}},\"zoom\":17,\"previousCoordinates\":null},\"mapInfo\":{\"geoSessionId\":\"ac3d569a-3dd5-4e65-a5ea-d99b34577b6e\",\"preferredGeoProviders\":{\"suggest\":[\"maps_selfsuggest\",\"yandex\"],\"geocode\":[\"maps_selfsuggest\",\"yandex\"],\"revGeocode\":[\"maps_selfsuggest\",\"yandex\"]}}}",
  "method": "POST",
  "mode": "cors",
  "credentials": "include"
}).then(() => true).catch(() => true);"""

_PRODUCT_KEYS = ("skuId", "sku", "cellTrackingInfo", "tileImage", "mainState", "status")


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


def _build_actions(
    query: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> list[dict[str, str]]:
    encoded = encode_query(query)
    search_url = (
        f"https://www.ozon.ru/search/?text={encoded}&from_global=true&{REFER}"
    )
    geo_script = _GEO_SCRIPT_TEMPLATE.replace("__CITY_INFO__", json.dumps(CITY_INFO))
    return [
        {"type": "url", "data": search_url},
        {"type": "wait", "data": "5000"},
        {"type": "waitElement", "data": geo_script, "wait_for": ""},
        {"type": "url", "data": _search_api_url(query, min_price=min_price, max_price=max_price)},
        {"type": "wait", "data": "3000"},
    ]


def _parse_widget_states(data: dict, products: list[MarketProduct]) -> None:
    states = data.get("widgetStates")
    if not isinstance(states, dict):
        return
    for raw_state in states.values():
        if not isinstance(raw_state, str):
            continue
        try:
            state = json.loads(raw_state)
        except json.JSONDecodeError:
            continue
        _parse_ozon_node(state, products)


def _parse_ozon_node(node: object, products: list[MarketProduct]) -> None:
    if isinstance(node, dict):
        if "items" in node and isinstance(node["items"], list):
            for item in node["items"]:
                _parse_ozon_item(item, products)
        if "tiles" in node and isinstance(node["tiles"], list):
            for tile in node["tiles"]:
                _parse_ozon_item(tile, products)
        for value in node.values():
            _parse_ozon_node(value, products)
    elif isinstance(node, list):
        for item in node:
            _parse_ozon_node(item, products)


def _parse_ozon_item(item: object, products: list[MarketProduct]) -> None:
    if not isinstance(item, dict):
        return
    parsed = product_from_dict(item)
    if parsed:
        append_product(products, parsed)
        return

    main_state = item.get("mainState")
    if not isinstance(main_state, list):
        return

    name = None
    price_str = None
    for block in main_state:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "textAtom":
            text = block.get("textAtom", {}).get("text")
            if isinstance(text, str):
                name = text.strip()
        if block.get("type") == "priceV2":
            price = block.get("priceV2", {}).get("price", [])
            if isinstance(price, list) and price:
                val = price[0].get("text") if isinstance(price[0], dict) else None
                if val:
                    price_str = re.sub(r"\D", "", val) or val
    if name:
        append_product(products, MarketProduct(name=name, price=price_str, image_link=None))


def _parse_ozon_payload(data: object) -> list[MarketProduct]:
    products: list[MarketProduct] = []
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


def parse_html(html: str) -> list[MarketProduct]:
    data = _extract_json_document(html)
    if data:
        ozon_products = _parse_ozon_payload(data)
        if ozon_products:
            return ozon_products

    pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.DOTALL)
    if pre_match:
        try:
            data = json.loads(pre_match.group(1).strip())
            if isinstance(data, dict):
                ozon_products = _parse_ozon_payload(data)
                if ozon_products:
                    return ozon_products
        except json.JSONDecodeError:
            pass

    return parse_result_pre(html, product_keys=_PRODUCT_KEYS)


def run_parser(
    user_input: str,
    *,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> list[MarketProduct]:
    """Run Ozon search and return parsed products."""
    return run_site_parser(
        site_name=SITE,
        actions=_build_actions(user_input, min_price=min_price, max_price=max_price),
        parse_html=parse_html,
        check_captcha=CHECK_CAPTCHA,
        headless_env=HEADLESS_ENV,
    )


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "tasty coffee в зернах"
    for product in run_parser(query):
        print(product.model_dump_json(ensure_ascii=False))
