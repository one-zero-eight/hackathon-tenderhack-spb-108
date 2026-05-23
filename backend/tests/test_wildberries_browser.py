"""Wildberries tests: unit (region) and live browser integration.

Unit:  uv run pytest tests/test_wildberries_browser.py -k Region -v
Browser: RUN_BROWSER_TESTS=1 uv run pytest tests/test_wildberries_browser.py -k Browser -v
"""

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_asyncio

from src.modules.search.common import RESULT_PRE_ID, close_browser_context, get_browser_context, open_browser_page
from src.modules.search.region_geo import get_city_geo, make_wb_setup_page
from src.modules.search.typofix import parse_wildberries_typofix, queries_differ
from src.modules.search.wildberries import (
    CHECK_CAPTCHA,
    HEADLESS_ENV,
    SITE,
    _build_actions,
    _build_search_url,
    _wb_specs_rich_enough,
    fetch_wb_detail_characteristics,
    parse_html,
    run_site_parser,
)

KAZAN = "Казань"
REGION_QUERY = "ноутбук"

THINKBOOK_QUERY = "ноутбук lenovo thinkbook 16"
TYPO_QUERY = "телефон ihone"
REGION = "Казань"

THINKBOOK_NAME_SNIPPETS = (
    "Thinkbook 16 G8 IAL Ul5 225U",
    "Thinkbook 16 G8 IAL Ul7 255H",
    "ThinkBook 16+ 2025",
    "ThinkBook 16 G7 ARP",
    "ThinkBook 16 G6 IRL",
)

DETAIL_903747859_URL = "https://www.wildberries.ru/catalog/903747859/detail.aspx"
DETAIL_903747859_SPECS = {
    "Цвет": "серый",
    "Форм-фактор ноутбука": "Ультрабук",
    "Модель": "ThinkBook 16+ 2025",
    "Серия ноутбуков": "ThinkBook",
    "Операционная система": "Windows 11 Home",
    "Диагональ экрана (дюйм)": "16",
    "Процессор": "Intel Core Ultra 9 285H",
    "Суммарный объем оперативной памяти (Гб)": "32 ГБ",
    "Объем накопителя SSD": "1 ТБ",
    "Стандарт Wi-Fi": "Wi-Fi 6E (802.11ax)",
}


class TestWildberriesRegion:
    def test_search_url_includes_dest_for_region(self):
        geo = get_city_geo(KAZAN)
        url = _build_search_url(REGION_QUERY, geo=geo)
        assert f"dest={geo.wb_dest}" in url

    def test_search_url_no_dest_without_region(self):
        url = _build_search_url(REGION_QUERY, geo=None)
        assert "dest=" not in url

    def test_actions_fetch_script_includes_dest(self):
        geo = get_city_geo(KAZAN)
        actions = _build_actions(REGION_QUERY, geo=geo)
        fetch = next(a for a in actions if a["type"] == "waitElement" and f"dest={geo.wb_dest}" in a["data"])
        assert fetch["wait_for"] == f"pre#{RESULT_PRE_ID}"
        assert actions[0]["data"] == _build_search_url(REGION_QUERY, geo=geo)

    async def test_setup_page_fulfills_get_geo_info(self):
        geo = get_city_geo(KAZAN)
        fake_body = '{"dest":-2133462,"address":"Казань"}'
        with patch("src.modules.search.region_geo.wb_geo_json_for", return_value=fake_body):
            setup = make_wb_setup_page(geo)

        page = _FakePage()
        await setup(page)
        assert len(page.route_handlers) == 1

        route = _FakeRoute("https://user-geo-data.wildberries.ru/get-geo-info?latitude=55.7")
        await page.route_handlers[0](route)
        assert route.fulfilled == {
            "status": 200,
            "content_type": "application/json",
            "body": fake_body,
        }

    async def test_setup_page_passes_through_other_requests(self):
        geo = get_city_geo(KAZAN)
        with patch("src.modules.search.region_geo.wb_geo_json_for", return_value="{}"):
            setup = make_wb_setup_page(geo)

        page = _FakePage()
        await setup(page)

        route = _FakeRoute("https://www.wildberries.ru/catalog/0/search.aspx")
        await page.route_handlers[0](route)
        assert route.continued
        assert route.fulfilled is None

    async def test_setup_page_skips_route_when_region_already_set(self):
        geo = get_city_geo(KAZAN)
        with patch("src.modules.search.region_geo.wb_geo_json_for", return_value="{}"):
            setup = make_wb_setup_page(geo)

        page = _FakePage(url="https://www.wildberries.ru/catalog/0/search.aspx", region_set=True)
        await setup(page)
        assert page.route_handlers == []


class _FakeRoute:
    def __init__(self, url: str):
        self.request = SimpleNamespace(url=url)
        self.fulfilled = None
        self.continued = False

    async def fulfill(self, **kwargs):
        self.fulfilled = kwargs

    async def continue_(self):
        self.continued = True


class _FakePage:
    def __init__(self, *, url: str = "about:blank", region_set: bool = False):
        self.url = url
        self._region_set = region_set
        self.route_handlers: list = []

    async def evaluate(self, _script: str) -> bool:
        return self._region_set

    async def route(self, _pattern: str, handler) -> None:
        self.route_handlers.append(handler)


@pytest_asyncio.fixture
async def browser_context():
    os.environ["WILDBERRIES_HEADLESS"] = "0"
    os.environ["SEARCH_HEADLESS"] = "0"
    await close_browser_context()
    context = await get_browser_context()
    yield context
    await close_browser_context()


async def _run_wb_search(context, query: str, *, region: str | None = None):
    geo = get_city_geo(region)
    return await run_site_parser(
        context,
        site_name=SITE,
        actions=_build_actions(query, geo=geo),
        parse_html=parse_html,
        parse_typofix=lambda html: parse_wildberries_typofix(html, original=query),
        original_query=query,
        check_captcha_expr=CHECK_CAPTCHA,
        headless_env=HEADLESS_ENV,
        enrich_characteristics=None,
        setup_page=make_wb_setup_page(geo) if geo else None,
    )


@pytest.mark.browser
@pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1",
    reason="set RUN_BROWSER_TESTS=1 to run live browser tests",
)
@pytest.mark.asyncio
class TestWildberriesBrowser:
    async def test_detail_903747859_dom_characteristics(self, browser_context):
        page = await open_browser_page()
        try:
            specs = await fetch_wb_detail_characteristics(page, DETAIL_903747859_URL)
        finally:
            await page.close()

        assert _wb_specs_rich_enough(specs), f"expected rich specs, got {len(specs)}: {list(specs)[:8]}"
        for name, value in DETAIL_903747859_SPECS.items():
            assert specs.get(name) == value, f"{name}: expected {value!r}, got {specs.get(name)!r}"

    async def test_search_thinkbook_16(self, browser_context):
        products, _, typofix = await _run_wb_search(browser_context, THINKBOOK_QUERY, region=REGION)
        names = [p.name for p in products[:20]]

        assert len(products) >= 5, f"expected search results, got {len(products)}"
        for snippet in THINKBOOK_NAME_SNIPPETS:
            assert any(snippet in name for name in names), (
                f"missing product matching {snippet!r} in top results: {names[:8]}"
            )
        if typofix:
            assert not queries_differ(THINKBOOK_QUERY, typofix) or "thinkbook" in typofix.casefold()

    async def test_search_typo_iphone(self, browser_context):
        products, _, typofix = await _run_wb_search(browser_context, TYPO_QUERY, region=REGION)

        assert len(products) >= 3, f"expected typo-corrected results, got {len(products)}"
        assert typofix is not None, "expected WB typofix suggestion"
        assert "iphone" in typofix.casefold(), f"unexpected typofix: {typofix!r}"
        assert queries_differ(TYPO_QUERY, typofix)
