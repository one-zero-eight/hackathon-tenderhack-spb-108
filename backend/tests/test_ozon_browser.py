"""Ozon tests: unit (region, DOM) and live browser integration.

Unit:   uv run pytest tests/test_ozon_browser.py -k "Region or Dom" -v
Browser: RUN_BROWSER_TESTS=1 uv run pytest tests/test_ozon_browser.py -k Browser -v
"""

import os
from pathlib import Path

import pytest
import pytest_asyncio

from src.modules.search.common import close_browser_context, get_browser_context, open_browser_page
from src.modules.search.ozon import (
    CHECK_CAPTCHA,
    HEADLESS_ENV,
    SITE,
    _build_actions,
    _build_search_url,
    _collect_ozon_products_from_dom,
    _enrich_ozon_characteristics,
    collect_ozon_products_from_page,
    fetch_ozon_detail_characteristics,
    parse_html,
    run_site_parser,
)
from src.modules.search.region_geo import (
    _OZON_BOOTSTRAP_URL,
    geo_for_marketplace_search,
    get_city_geo,
    make_ozon_setup_page,
    ozon_geo_page_url,
)
from src.modules.search.typofix import parse_ozon_typofix, queries_differ

KAZAN = "Казань"
REGION_QUERY = "ноутбук"

THINKBOOK_QUERY = "ноутбук lenovo thinkbook 16"
TYPO_QUERY = "телефон ihone"
REGION = "Казань"

# Live ThinkBook SERP after scroll usually has 4+ lazy grids (~32 tiles); no hard cap in parser.
_MIN_THINKBOOK_PRODUCTS = 24

THINKBOOK_NAME_SNIPPETS = (
    "ThinkBook",
    "Thinkbook",
    "Lenovo",
)

DETAIL_PRODUCT_URL = (
    "https://www.ozon.ru/product/"
    "lenovo-thinkbook-16-g6-irl-noutbuk-16-intel-core-ultra-5-125u-ram-16-gb-ssd-512-gb-intel-3463205841/"
)
DETAIL_SPECS = {
    "Процессор": "Intel Core Ultra 5 125U",
    "Общий объем SSD, ГБ": "512",
    "Видеокарта": "Intel Arc Graphics",
    "Артикул": "3463205841",
}


class TestOzonRegion:
    def test_search_url_encodes_query(self):
        url = _build_search_url(THINKBOOK_QUERY)
        assert "text=" in url
        assert url.startswith("https://www.ozon.ru/search/")

    def test_actions_include_geo_bootstrap_when_region(self):
        geo = get_city_geo(KAZAN)
        actions = _build_actions(REGION_QUERY, geo=geo)
        assert actions[0]["data"] == _OZON_BOOTSTRAP_URL
        geo_page = ozon_geo_page_url(geo)
        assert geo_page
        assert any(a.get("data") == geo_page for a in actions)
        assert any(a["type"] == "url" and "search" in a["data"] for a in actions)

    def test_actions_search_only_without_region(self):
        actions = _build_actions(REGION_QUERY, geo=None)
        assert actions[0]["type"] == "url"
        assert actions[0]["data"].startswith("https://www.ozon.ru/search/")


class TestOzonDom:
    @pytest.mark.asyncio
    async def test_collect_dom_tiles_from_saved_search_html(self):
        from playwright.async_api import async_playwright

        html_path = Path(__file__).resolve().parents[1] / "src/modules/search/out/ozon/html/step_10.html"
        if not html_path.is_file():
            pytest.skip(f"missing fixture HTML: {html_path}")

        html = html_path.read_text(encoding="utf-8", errors="replace")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html, wait_until="domcontentloaded")
            products = await _collect_ozon_products_from_dom(page)
            await browser.close()

        assert len(products) >= _MIN_THINKBOOK_PRODUCTS
        assert all(p.product_link and "/product/" in p.product_link for p in products)
        assert all(p.name and p.price for p in products)


@pytest_asyncio.fixture
async def browser_context():
    os.environ["OZON_HEADLESS"] = "0"
    os.environ["SEARCH_HEADLESS"] = "0"
    await close_browser_context()
    context = await get_browser_context()
    yield context
    await close_browser_context()


async def _run_ozon_search(context, query: str, *, region: str | None = None):
    geo = geo_for_marketplace_search(region)

    async def collect_from_page(page):
        return await collect_ozon_products_from_page(page, search_query=query)

    return await run_site_parser(
        context,
        site_name=SITE,
        actions=_build_actions(query, geo=geo),
        parse_html=parse_html,
        parse_typofix=lambda html: parse_ozon_typofix(html, original=query),
        original_query=query,
        check_captcha_expr=CHECK_CAPTCHA,
        headless_env=HEADLESS_ENV,
        enrich_characteristics=None,
        setup_page=make_ozon_setup_page(geo) if geo and geo.ozon_slug else None,
        collect_dom_products=collect_from_page,
    )


async def _run_ozon_search_with_enrich(context, query: str, *, region: str | None = None):
    geo = geo_for_marketplace_search(region)

    async def collect_from_page(page):
        return await collect_ozon_products_from_page(page, search_query=query)

    return await run_site_parser(
        context,
        site_name=SITE,
        actions=_build_actions(query, geo=geo),
        parse_html=parse_html,
        parse_typofix=lambda html: parse_ozon_typofix(html, original=query),
        original_query=query,
        check_captcha_expr=CHECK_CAPTCHA,
        headless_env=HEADLESS_ENV,
        enrich_characteristics=_enrich_ozon_characteristics,
        setup_page=make_ozon_setup_page(geo) if geo and geo.ozon_slug else None,
        collect_dom_products=collect_from_page,
    )


@pytest.mark.browser
@pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1",
    reason="set RUN_BROWSER_TESTS=1 to run live browser tests",
)
@pytest.mark.asyncio
class TestOzonBrowser:
    async def test_detail_thinkbook_characteristics(self, browser_context):
        page = await open_browser_page()
        try:
            specs = await fetch_ozon_detail_characteristics(page, DETAIL_PRODUCT_URL)
        finally:
            await page.close()

        assert len(specs) >= 10, f"expected rich specs, got {len(specs)}: {list(specs)[:8]}"
        for name, value in DETAIL_SPECS.items():
            assert specs.get(name) == value, f"{name}: expected {value!r}, got {specs.get(name)!r}"

    async def test_search_thinkbook_16_product_count(self, browser_context):
        products, _, _ = await _run_ozon_search(browser_context, THINKBOOK_QUERY, region=REGION)

        assert len(products) >= _MIN_THINKBOOK_PRODUCTS, (
            f"expected at least {_MIN_THINKBOOK_PRODUCTS} loaded products, got {len(products)}"
        )
        for product in products:
            assert product.name and product.name.strip()
            assert product.product_link and "/product/" in product.product_link
            assert product.price

    async def test_search_thinkbook_16(self, browser_context):
        products, _, typofix = await _run_ozon_search(browser_context, THINKBOOK_QUERY, region=REGION)
        names = [p.name for p in products[:32]]

        assert len(products) >= 8, f"expected search results, got {len(products)}"
        assert any(any(snippet in name for name in names) for snippet in THINKBOOK_NAME_SNIPPETS), (
            f"no ThinkBook/Lenovo in results: {names[:8]}"
        )
        if typofix:
            assert not queries_differ(THINKBOOK_QUERY, typofix) or "thinkbook" in typofix.casefold()

    async def test_search_typo_iphone(self, browser_context):
        products, _, typofix = await _run_ozon_search(browser_context, TYPO_QUERY, region=REGION)

        assert len(products) >= 3, f"expected typo-corrected results, got {len(products)}"
        assert typofix is not None, "expected Ozon typofix suggestion"
        assert "iphone" in typofix.casefold(), f"unexpected typofix: {typofix!r}"
        assert queries_differ(TYPO_QUERY, typofix)

    async def test_full_pipeline_with_enrich(self, browser_context):
        """Scroll + API pagination + per-product detail enrichment."""
        products, _, _ = await _run_ozon_search_with_enrich(browser_context, THINKBOOK_QUERY, region=REGION)
        enriched = [p for p in products if p.characteristics]
        assert len(products) >= 8, f"expected search results, got {len(products)}"
        assert len(enriched) >= 1, "expected at least one product with enriched characteristics"
