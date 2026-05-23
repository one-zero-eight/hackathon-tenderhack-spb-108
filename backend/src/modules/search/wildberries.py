"""Wildberries search parser using cloakbrowser."""

import json
from urllib.parse import quote

from src.modules.search.schemas import SearchSource

from .common import (
    DEFAULT_MAX_PRICE,
    DEFAULT_MIN_PRICE,
    RESULT_PRE_ID,
    TYPOFIX_PRE_ID,
    SearchResult,
    append_product,
    build_price_filter,
    encode_query,
    extract_pre_content,
    page_content,
    parse_api_payload,
    parse_result_pre,
    run_site_parser,
)
from .details import enrich_product_characteristics, parse_specs_table_html, specs_from_raw
from .region_geo import get_city_geo, make_wb_setup_page
from .typofix import parse_wildberries_typofix, queries_differ

_WB_DETAIL_SPECS_JS = """() => {
  const out = [];
  const seen = new Set();
  const add = (name, value) => {
    const key = name + '\\0' + value;
    if (!name || !value || seen.has(key)) return;
    seen.add(key);
    out.push([name, value]);
  };
  const skip = new Set(['Дополнительная информация', 'Габариты', 'Основные характеристики']);
  document.querySelectorAll('th[class*="cellKey"]').forEach(th => {
    const tr = th.closest('tr');
    const td = tr && tr.querySelector('td[class*="cellValue"]');
    if (td) add(th.innerText.trim(), td.innerText.trim());
  });
  const section = [...document.querySelectorAll('section')].find(
    s => s.innerText.includes('Ширина, мм') || s.innerText.includes('Артикул')
  );
  if (section) {
    const lines = section.innerText.split('\\n').map(l => l.trim()).filter(Boolean);
    for (let i = 0; i < lines.length - 1; i++) {
      if (skip.has(lines[i])) continue;
      if (!skip.has(lines[i + 1])) {
        add(lines[i], lines[i + 1]);
        i++;
      }
    }
  }
  document.querySelectorAll('[class*="param"]').forEach(el => {
    const parts = [...el.children].map(c => c.innerText.trim()).filter(Boolean);
    if (parts.length >= 2) add(parts[0], parts[1]);
  });
  return out;
}"""

_DISMISS_BLOCKING_DRAWER_STMTS = """const overlay = document.querySelector('.mo-drawer__overlay');
if (!overlay) return false;
if (document.querySelector('th[class*="cellKey"]')) return false;
const close = document.querySelector('[class*="closeButton"]')
  || document.querySelector('.mo-drawer__paper button[type="button"]');
if (close) {
  close.click();
  return true;
}
overlay.click();
return true;"""

_DISMISS_BLOCKING_DRAWER_JS = f"() => {{ {_DISMISS_BLOCKING_DRAWER_STMTS} }}"

SITE = "wildberries"
CHECK_CAPTCHA = "document.querySelector('#wait_msg') != null || document.querySelector('.support-title') != null"
HEADLESS_ENV = "WILDBERRIES_HEADLESS"

_WAIT_QUERY_ID = r"""function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

async function waitForElement(timeout = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    let queryId = sessionStorage.query_id_search != null && sessionStorage.query_id_search != '';
    let wbaas = null;
    try {
      wbaas = getCookie('x_wbaas_token');
    } catch (_) {}
    let powToken = false;
    try {
      powToken = localStorage.getItem('session-pow-token') != null && localStorage.getItem('session-pow-token') != '';
    } catch (_) {}
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
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  return false;
}

return await waitForElement();"""

_WAIT_FETCH_TEMPLATE = r"""async function runSearchFetch() {
  const originalQuery = __ORIGINAL_QUERY__;
  function normalizeQuery(text) {
    return (text || '').trim().replace(/\\s+/g, ' ').toLowerCase();
  }

  function readCorrectedQuery() {
    const searchInput = document.querySelector('#searchInput');
    if (searchInput && searchInput.value) {
      const inputValue = searchInput.value.trim();
      if (inputValue && normalizeQuery(inputValue) !== normalizeQuery(originalQuery)) {
        return inputValue;
      }
    }
    const correctedEl = document.querySelector(
      '.searching-results__query-replaced .searching-results__query'
    );
    if (correctedEl) {
      const corrected = correctedEl.textContent.replace(/[«»]/g, '').trim();
      if (corrected && normalizeQuery(corrected) !== normalizeQuery(originalQuery)) {
        return corrected;
      }
    }
    return null;
  }

  function pageReady() {
    const queryIdEl = document.querySelector('#queryId');
    if (!queryIdEl || !queryIdEl.textContent) {
      return false;
    }
    return !!(
      document.querySelector('[data-nm-id]') ||
      document.querySelector('.product-card__wrapper') ||
      document.querySelector('.catalog-page__content')
    );
  }

  let correctedQuery = readCorrectedQuery();
  if (!correctedQuery) {
    for (let attempt = 0; attempt < 8; attempt++) {
      if (pageReady()) {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 200));
      correctedQuery = readCorrectedQuery();
      if (correctedQuery) {
        break;
      }
    }
  }

  let queryEnc = correctedQuery
    ? encodeURIComponent(correctedQuery)
    : "__QUERY_ENC__";

  function hasProductCards() {
    return !!(
      document.querySelector('[data-nm-id]') ||
      document.querySelector('.product-card__wrapper')
    );
  }

  function isEmptySearchPage() {
    if (hasProductCards()) {
      return false;
    }
    if (document.querySelector('.content404')) {
      return true;
    }
    const countEl = document.querySelector('.searching-results__count');
    if (
      countEl &&
      !countEl.classList.contains('hide') &&
      countEl.textContent.trim() === '0 товаров найдено'
    ) {
      return true;
    }
    return document.querySelector('.not-found-search__title') != null;
  }

  if (isEmptySearchPage()) {
    document.body = document.createElement("body");
    if (correctedQuery) {
      const typoPre = document.createElement('pre');
      typoPre.id = "__TYPOFIX_PRE_ID__";
      typoPre.innerText = correctedQuery;
      document.body.append(typoPre);
    }
    const g = document.createElement('pre');
    g.setAttribute("id", "__PRE_ID__");
    g.innerHTML = 'not found';
    document.body.append(g);
    return true;
  }

  const priceFilter = __PRICE_FILTER_JS__;
  const queryId = document.querySelector('#queryId');
  const powToken = document.querySelector('#powToken')
    ? document.querySelector('#powToken').textContent
    : null;
  const apiUrl = "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search?ab_testing=false&appType=1&curr=rub&__DEST_PARAM__hide_dtype=11&inheritFilters=false&lang=ru&page=1" + priceFilter + "&query=" + queryEnc + "&resultset=catalog&sort=popular&spp=30&suppressSpellcheck=false";
  const referrer = "https://www.wildberries.ru/catalog/0/search.aspx?__DEST_PARAM__search=" + queryEnc;

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

  try {
    const response = await fetch(apiUrl, {
      "headers": headers,
      "referrer": referrer,
      "method": "GET",
      "mode": "cors",
      "credentials": "include"
    });
    const data = await response.text();
    document.body = document.createElement("body");
    if (correctedQuery) {
      const typoPre = document.createElement('pre');
      typoPre.id = "__TYPOFIX_PRE_ID__";
      typoPre.innerText = correctedQuery;
      document.body.append(typoPre);
    }
    const g = document.createElement('pre');
    g.setAttribute("id", "__PRE_ID__");
    g.innerText = data;
    document.body.append(g);
    return true;
  } catch (error) {
    document.body = document.createElement('body');
    const g = document.createElement('pre');
    g.setAttribute("id", "__PRE_ID__");
    g.innerText = 'error: ' + error;
    document.body.append(g);
    return true;
  }
}

return await runSearchFetch();"""

_PRODUCT_KEYS = ("name", "salePriceU", "priceU", "brand", "id", "pics", "sizes")

# vol upper bound -> basket-NN.wbbasket.ru (wh in API is warehouse id, not CDN host)
_WB_BASKET_VOL_LIMITS = (
    143,
    287,
    431,
    719,
    1007,
    1061,
    1115,
    1169,
    1313,
    1601,
    1655,
    1919,
    2045,
    2189,
    2405,
    2621,
    2837,
    3053,
    3269,
    3485,
    3701,
    3917,
    4133,
    4349,
    4565,
    4877,
    5189,
    5501,
    5813,
    6125,
    6437,
    6749,
    7061,
    7373,
    7685,
    7997,
    8309,
    8621,
    8933,
    9245,
    9557,
    9869,
    10181,
    10493,
    10805,
    11117,
    11429,
    11741,
    12053,
    12365,
    12677,
    12989,
    13301,
    13613,
    13925,
    14237,
    14549,
    14861,
    15173,
    15485,
    15797,
    16109,
    16421,
    16733,
    17045,
    17357,
    17669,
    17981,
    18293,
    18605,
    18917,
    19229,
    19541,
    19853,
    20165,
    20477,
    20789,
    21101,
    21413,
    21725,
    22037,
    22349,
    22661,
    22973,
    23285,
    23597,
    23909,
    24221,
    24533,
    24845,
    25157,
    25469,
    25781,
    26093,
    26405,
    26717,
    27029,
    27341,
    27653,
    27965,
    28277,
    28589,
    28901,
    29213,
    29525,
    29837,
    30149,
    30461,
    30773,
    31085,
    31397,
    31709,
    32021,
    32333,
    32645,
    32957,
    33269,
    33581,
    33893,
    34205,
    34517,
    34829,
    35141,
    35453,
    35765,
    36077,
    36389,
    36701,
    37013,
    37325,
    37637,
    37949,
    38261,
    38573,
    38885,
    39197,
    39509,
    39821,
    40133,
    40445,
    40757,
    41069,
    41381,
    41693,
    42005,
    42317,
    42629,
    42941,
    43253,
    43565,
    43877,
    44189,
    44501,
    44813,
    45125,
    45437,
    45749,
    46061,
    46373,
    46685,
    46997,
    47309,
    47621,
    47933,
    48245,
    48557,
    48869,
    49181,
    49493,
    49805,
    50117,
    50429,
    50741,
    51053,
    51365,
    51677,
    51989,
    52301,
    52613,
    52925,
    53237,
    53549,
    53861,
    54173,
    54485,
    54797,
    55109,
    55421,
    55733,
    56045,
    56357,
    56669,
    56981,
    57293,
    57605,
    57917,
    58229,
    58541,
    58853,
    59165,
    59477,
    59789,
    60101,
    60413,
    60725,
    61037,
    61349,
    61661,
    61973,
    62285,
    62597,
    62909,
    63221,
    63533,
    63845,
    64157,
    64469,
    64781,
    65093,
    65405,
    65717,
    66029,
    66341,
    66653,
    66965,
    67277,
    67589,
    67901,
    68213,
    68525,
    68837,
    69149,
    69461,
    69773,
    70085,
    70397,
    70709,
    71021,
    71333,
    71645,
    71957,
    72269,
    72581,
)


def _wb_price_filter_js(
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> str:
    if min_price <= 0 and max_price >= DEFAULT_MAX_PRICE:
        return "''"
    return json.dumps(build_price_filter("&priceU=[minPrice];[maxPrice]", min_price=min_price, max_price=max_price))


def _dest_query(geo) -> str:
    return f"dest={geo.wb_dest}&" if geo else ""


def _build_search_url(query: str, *, geo=None) -> str:
    encoded = encode_query(query)
    dest = _dest_query(geo)
    return f"https://www.wildberries.ru/catalog/0/search.aspx?page=1&{dest}search={encoded}"


def _build_actions(
    query: str,
    *,
    geo=None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> list[dict[str, str]]:
    search_url = _build_search_url(query, geo=geo)
    dest_param = _dest_query(geo)
    fetch_script = (
        _WAIT_FETCH_TEMPLATE.replace("__PRE_ID__", RESULT_PRE_ID)
        .replace("__TYPOFIX_PRE_ID__", TYPOFIX_PRE_ID)
        .replace("__DEST_PARAM__", dest_param)
        .replace("__QUERY_ENC__", quote(query))
        .replace("__ORIGINAL_QUERY__", json.dumps(query))
        .replace("__PRICE_FILTER_JS__", _wb_price_filter_js(min_price, max_price))
    )
    return [
        {"type": "url", "data": search_url},
        {
            "type": "script",
            "data": _DISMISS_BLOCKING_DRAWER_STMTS,
            "expects_navigation": "false",
        },
        {"type": "waitFor", "data": "#searchInput", "timeout": "20000"},
        {"type": "waitElement", "data": _WAIT_QUERY_ID, "wait_for": "pre#queryId"},
        {"type": "waitFor", "data": "[data-nm-id], .product-card__wrapper", "timeout": "15000"},
        {
            "type": "waitElement",
            "data": fetch_script,
            "wait_for": f"pre#{RESULT_PRE_ID}",
        },
    ]


def _wb_basket_host(vol: int) -> str:
    for index, limit in enumerate(_WB_BASKET_VOL_LIMITS, start=1):
        if vol <= limit:
            return f"{index:02d}"
    return f"{len(_WB_BASKET_VOL_LIMITS) + 1:02d}"


def _wb_price_kopecks(item: dict) -> int | None:
    for key in ("salePriceU", "priceU"):
        value = item.get(key)
        if isinstance(value, int):
            return value
    sizes = item.get("sizes")
    if not isinstance(sizes, list):
        return None
    prices: list[int] = []
    for size in sizes:
        if not isinstance(size, dict):
            continue
        price_block = size.get("price")
        if not isinstance(price_block, dict):
            continue
        for key in ("product", "basic"):
            value = price_block.get(key)
            if isinstance(value, int):
                prices.append(value)
                break
    return min(prices) if prices else None


def _wb_image_url(product: dict) -> str | None:
    nm_id = product.get("id") or product.get("nmId")
    if not nm_id:
        return None
    nm_id = int(nm_id)
    vol = nm_id // 100_000
    part = nm_id // 1_000
    host = _wb_basket_host(vol)
    return f"https://basket-{host}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/big/1.webp"


def parse_wb_detail_html(html: str) -> dict[str, str]:
    return parse_specs_table_html(html)


async def _extract_wb_specs(page) -> dict[str, str]:
    specs = specs_from_raw(await page.evaluate(_WB_DETAIL_SPECS_JS))
    if specs:
        return specs
    return parse_wb_detail_html(await page_content(page))


async def dismiss_wb_blocking_drawer(page) -> None:
    dismissed = await page.evaluate(_DISMISS_BLOCKING_DRAWER_JS)
    if dismissed:
        try:
            await page.wait_for_selector(".mo-drawer__overlay", state="hidden", timeout=3_000)
        except Exception:
            pass


async def fetch_wb_detail_characteristics(page, product_link: str) -> dict[str, str]:
    await page.goto(product_link, wait_until="domcontentloaded", timeout=30_000)
    await dismiss_wb_blocking_drawer(page)
    if await page.locator("th[class*='cellKey']").count() > 0:
        specs = await _extract_wb_specs(page)
        if specs:
            return specs
    try:
        await page.locator("button").filter(has_text="Характеристики").first.click(timeout=5_000)
    except Exception:
        pass
    try:
        await page.wait_for_selector("th.cellKey--eGe6N, th[class*='cellKey']", timeout=5_000)
    except Exception:
        pass
    return await _extract_wb_specs(page)


async def _enrich_wb_characteristics(page, products: list[SearchResult]) -> None:
    await enrich_product_characteristics(
        page,
        products,
        fetch_characteristics=fetch_wb_detail_characteristics,
        check_captcha_expr=CHECK_CAPTCHA,
        site_name=SITE,
    )


def _product_from_wb(item: dict) -> SearchResult | None:
    name = item.get("name")
    if not name:
        return None
    brand = item.get("brand")
    if brand:
        name = f"{brand} {name}".strip()

    price = _wb_price_kopecks(item)
    price_str = str(price // 100) if isinstance(price, int) else None

    rating = str(item["rating"]) if item.get("rating") is not None else None
    reviews = str(item["feedbacks"]) if item.get("feedbacks") is not None else None
    nm_id = item.get("id") or item.get("nmId")
    product_link = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx" if nm_id is not None else None

    return SearchResult(
        name=str(name).strip(),
        product_link=product_link,
        price=price_str,
        image_link=_wb_image_url(item),
        rating=rating,
        reviews=reviews,
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


async def run_wildberries_parser(
    context,
    user_input: str,
    *,
    region: str | None = None,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> tuple[SearchSource, str | None]:
    """Run Wildberries search and return parsed products."""
    geo = get_city_geo(region)

    async def run_for_query(query: str):
        return await run_site_parser(
            context,
            site_name=SITE,
            actions=_build_actions(query, geo=geo, min_price=min_price, max_price=max_price),
            parse_html=parse_html,
            parse_typofix=lambda html: parse_wildberries_typofix(html, original=user_input),
            original_query=user_input,
            check_captcha_expr=CHECK_CAPTCHA,
            headless_env=HEADLESS_ENV,
            enrich_characteristics=_enrich_wb_characteristics,
            setup_page=make_wb_setup_page(geo) if geo else None,
        )

    # Query is usually already corrected via routes (Ozon typofix); fetch script applies spellcheck once.
    results, timing, typofix = await run_for_query(user_input)

    search_query = typofix if typofix and queries_differ(user_input, typofix) else user_input
    return SearchSource(
        source_type="wildberries",
        source_url=_build_search_url(search_query, geo=geo),
        source_title="Wildberries",
        source_favicon_url=None,
        results=results,
        timing=timing,
    ), typofix


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "tasty coffee в зернах"
    results = run_wildberries_parser(query)
    print(results.model_dump_json(ensure_ascii=False))
