"""Yandex Market tests: unit (region) and live browser integration.

Unit:   uv run pytest tests/test_yandex_market_browser.py -k Region -v
Browser: RUN_BROWSER_TESTS=1 uv run pytest tests/test_yandex_market_browser.py -k Browser -v
"""

import os

import pytest
import pytest_asyncio

from src.modules.search.common import close_browser_context, get_browser_context, open_browser_page
from src.modules.search.region_geo import get_city_geo, make_yandex_setup_page, yandex_sync_region_ui_script
from src.modules.search.typofix import parse_yandex_market_typofix, queries_differ
from src.modules.search.yandex_market import (
    CHECK_CAPTCHA,
    HEADLESS_ENV,
    SITE,
    _build_actions,
    _build_search_url,
    collect_products_from_page,
    fetch_yandex_detail_characteristics,
    run_site_parser,
)

KAZAN = "Казань"
REGION_QUERY = "ноутбук"

THINKBOOK_QUERY = "ноутбук lenovo thinkbook 16"
TYPO_QUERY = "телефон ihone"
REGION = "Казань"

THINKBOOK_NAME_SNIPPETS = (
    "8845H (5.1 ГГц), RAM 24 ГБ DDR5, SSD 1024 ГБ",
    "8845H (5.1 ГГц), RAM 24 ГБ LPDDR5",
    'ThinkBook 16 G8 IAL 16"/Core Ultra 7 255H/16Гб/512Гб',
)

DETAIL_4926170909_URL = (
    "https://market.yandex.ru/card/"
    "16-noutbuk-lenovo-thinkbook-16-2560x1600-ips-120gts-amd-ryzen-7-8845h-51-ggts-"
    "ram-32-gb-lpddr5kh-ssd-1024-gb-amd-radeon-780m-windows-11-pro--ms-office-pro-"
    "seryy-russkaya-raskladka/4926170909"
)
DETAIL_4926170909_SPECS = {
    "Бренд": "Lenovo",
    "Линейка": "ThinkBook",
    "Операционная система": "Windows 11 Pro",
    "Процессор": "AMD Ryzen 7 8845H",
    "Оперативная память": "24 ГБ",
    "Диагональ экрана": '16"',
    "Разрешение экрана": "2560x1600",
    "Общий объем накопителей SSD": "1 ТБ",
}


class TestYandexMarketRegion:
    def test_search_url_includes_lr_for_region(self):
        geo = get_city_geo(KAZAN)
        url = _build_search_url(REGION_QUERY, geo=geo)
        assert f"lr={geo.yandex_lr}" in url

    def test_search_url_no_lr_without_region(self):
        url = _build_search_url(REGION_QUERY, geo=None)
        assert "lr=" not in url

    def test_actions_include_region_sync_script(self):
        geo = get_city_geo(KAZAN)
        sync_script = yandex_sync_region_ui_script(geo)
        actions = _build_actions(REGION_QUERY, geo=geo)
        sync = next(a for a in actions if a.get("data") == sync_script)
        assert sync["type"] == "waitElement"
        assert f"lr={geo.yandex_lr}" in actions[0]["data"]

    def test_actions_skip_region_sync_without_geo(self):
        actions = _build_actions(REGION_QUERY, geo=None)
        sync_script = yandex_sync_region_ui_script(get_city_geo(KAZAN))
        assert not any(a.get("data") == sync_script for a in actions)


@pytest_asyncio.fixture
async def browser_context():
    os.environ["YANDEX_MARKET_HEADLESS"] = "0"
    os.environ["SEARCH_HEADLESS"] = "0"
    await close_browser_context()
    context = await get_browser_context()
    yield context
    await close_browser_context()


async def _run_ym_search(context, query: str, *, region: str | None = None):
    geo = get_city_geo(region)
    return await run_site_parser(
        context,
        site_name=SITE,
        actions=_build_actions(query, geo=geo),
        parse_html=lambda _: [],
        parse_typofix=lambda html: parse_yandex_market_typofix(html, original=query),
        original_query=query,
        check_captcha_expr=CHECK_CAPTCHA,
        headless_env=HEADLESS_ENV,
        enrich_characteristics=None,
        setup_page=make_yandex_setup_page(geo) if geo else None,
        collect_dom_products=collect_products_from_page,
    )


@pytest.mark.browser
@pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1",
    reason="set RUN_BROWSER_TESTS=1 to run live browser tests",
)
@pytest.mark.asyncio
class TestYandexMarketBrowser:
    async def test_detail_4926170909_characteristics(self, browser_context):
        page = await open_browser_page()
        try:
            specs = await fetch_yandex_detail_characteristics(page, DETAIL_4926170909_URL)
        finally:
            await page.close()

        assert len(specs) >= 15, f"expected rich specs, got {len(specs)}: {list(specs)[:8]}"
        for name, value in DETAIL_4926170909_SPECS.items():
            assert specs.get(name) == value, f"{name}: expected {value!r}, got {specs.get(name)!r}"

    async def test_search_thinkbook_16(self, browser_context):
        products, _, typofix = await _run_ym_search(browser_context, THINKBOOK_QUERY, region=REGION)
        names = [p.name for p in products[:20]]

        assert len(products) >= 3, f"expected search results, got {len(products)}"
        for snippet in THINKBOOK_NAME_SNIPPETS:
            assert any(snippet in name for name in names), (
                f"missing product matching {snippet!r} in top results: {names[:8]}"
            )
        if typofix:
            assert not queries_differ(THINKBOOK_QUERY, typofix) or "thinkbook" in typofix.casefold()

    async def test_search_typo_iphone(self, browser_context):
        products, _, typofix = await _run_ym_search(browser_context, TYPO_QUERY, region=REGION)

        assert len(products) >= 3, f"expected typo-corrected results, got {len(products)}"
        assert typofix is not None, "expected Yandex Market typofix suggestion"
        assert "iphone" in typofix.casefold(), f"unexpected typofix: {typofix!r}"
        assert queries_differ(TYPO_QUERY, typofix)
        names = " ".join(p.name.casefold() for p in products[:10])
        assert "iphone" in names or "айфон" in names, f"results don't look like iphone search: {names[:200]}"
