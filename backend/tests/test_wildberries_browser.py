"""Live Wildberries integration tests (cloakbrowser, headful).

Run: RUN_BROWSER_TESTS=1 uv run pytest tests/test_wildberries_browser.py -v
"""

import os

import pytest
import pytest_asyncio

from src.modules.search.common import close_browser_context, get_browser_context, open_browser_page
from src.modules.search.region_geo import get_city_geo, make_wb_setup_page
from src.modules.search.typofix import parse_wildberries_typofix, queries_differ
from src.modules.search.wildberries import (
    CHECK_CAPTCHA,
    HEADLESS_ENV,
    SITE,
    _build_actions,
    _wb_specs_rich_enough,
    fetch_wb_detail_characteristics,
    parse_html,
    run_site_parser,
)

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("RUN_BROWSER_TESTS") != "1",
        reason="set RUN_BROWSER_TESTS=1 to run live browser tests",
    ),
    pytest.mark.asyncio,
]

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
