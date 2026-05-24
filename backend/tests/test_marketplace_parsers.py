import json
from pathlib import Path

import pytest

from src.modules.search.common import SearchResult, _merge_typofix_suggestion, normalize_display_text
from src.modules.search.ozon import parse_html as parse_ozon_html
from src.modules.search.ozon import parse_ozon_detail_html
from src.modules.search.typofix import (
    parse_ozon_typofix,
    parse_wildberries_typofix,
    parse_yandex_market_typofix,
)
from src.modules.search.wildberries import (
    _wb_specs_rich_enough,
    parse_wb_card_options,
    parse_wb_detail_html,
)
from src.modules.search.wildberries import parse_html as parse_wb_html
from src.modules.search.yandex_market import (
    _dedupe_yandex_products,
    collect_products_from_page,
    parse_yandex_detail_html,
)
from src.modules.search.yandex_market import (
    parse_html as parse_yandex_html,
)
from tests.conftest import example_html, fixture_json


class TestYandexMarket:
    def test_normalize_display_text_decodes_double_encoded_entities(self):
        assert normalize_display_text("16&amp;quot; Laptop") == '16" Laptop'
        assert normalize_display_text("foo&nbsp;bar") == "foo bar"

    def test_parse_snippet_spec_lines(self):
        text = (
            '16" Ноутбук Lenovo\n'
            'Диагональ экрана: 16"\n'
            "Процессор: AMD Ryzen 7 8845H\n"
            "Рейтинг товара: 4.9 из 5\n"
            "73 238 ₽\n"
        )
        from src.modules.search.yandex_market import _parse_snippet_spec_lines

        specs = _parse_snippet_spec_lines(text)
        assert specs["Диагональ экрана"] == '16"'
        assert specs["Процессор"] == "AMD Ryzen 7 8845H"
        assert "Рейтинг" not in "".join(specs)
        assert "detail" not in specs

    def test_parse_snippet_spec_lines_rejects_script_junk(self):
        from src.modules.search.yandex_market import _parse_snippet_spec_lines

        text = (
            'detail: data\n})({"event":"mount_cpm_node_event","data":{"showUrl":["/abc:2"]}}\nДиагональ экрана: 6.1"\n'
        )
        specs = _parse_snippet_spec_lines(text)
        assert specs == {"Диагональ экрана": '6.1"'}

    def test_dedupe_merges_nested_snippets_by_card_id(self):
        link = "https://market.yandex.ru/card/foo/5225693002"
        merged = _dedupe_yandex_products(
            [
                SearchResult(
                    name='Ноутбук Lenovo ThinkBook 16 G8 IAL 16"',
                    product_link=link,
                    price="80737",
                    image_link="https://avatars.mds.yandex.net/get-mpic/1/abc/orig",
                ),
                SearchResult(
                    name="Product",
                    product_link=link,
                    image_link="https://avatars.mds.yandex.net/get-mpic/2/def/orig",
                ),
            ]
        )
        assert len(merged) == 1
        assert "Lenovo" in merged[0].name
        assert merged[0].price == "80737"

    def test_yandex_link_from_filter(self):
        from src.modules.search.yandex_market import _should_skip_yandex_product_link

        assert not _should_skip_yandex_product_link("https://market.yandex.ru/card/foo/1?from=search")
        assert _should_skip_yandex_product_link("https://market.yandex.ru/card/foo/2?from=premiumOffers")

    def test_product_card_specs(self):
        specs = parse_yandex_detail_html(example_html("16_*ин.html"))
        assert len(specs) >= 10
        assert specs.get("Артикул Маркета") == "4926170907"
        assert specs.get("Бренд") == "Lenovo"
        assert "Диагональ экрана" in specs

    def test_search_url_respects_spellcheck_flag(self):
        from src.modules.search.yandex_market import _YANDEX_NO_CORRECTION_RS, _build_search_url

        query = "телефон ihone"
        with_correction = _build_search_url(query, spellcheck=True)
        assert "cvredirect=1" in with_correction
        assert "rs=" not in with_correction

        no_correction = _build_search_url(query, spellcheck=False)
        assert "cvredirect=1" not in no_correction
        assert f"rs={_YANDEX_NO_CORRECTION_RS}" in no_correction

    @pytest.mark.asyncio
    async def test_collect_products_from_page_fixture(self):
        from playwright.async_api import async_playwright

        html = example_html("Ноутбук Lenovo Thinkbook 16 — купить по низкой цене на Яндекс Маркете.html")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html, wait_until="domcontentloaded")
            products = await collect_products_from_page(page)
            await browser.close()

        assert len(products) >= 3
        assert all(product.product_link and "/card/" in product.product_link for product in products[:3])
        with_images = [product for product in products if product.image_link]
        if any("get-mpic" in (product.image_link or "") for product in with_images):
            assert all("get-mpic" in (product.image_link or "") for product in with_images[:3])
            assert all("get-marketcms" not in (product.image_link or "") for product in with_images[:3])
            assert all(product.image_link not in product.image_links for product in with_images[:3])
        assert not any(product.name.strip().casefold() == "product" for product in products)
        assert all(product.price for product in products[:3])
        assert products[0].characteristics.get("Процессор")

    def test_picture_gallery_images_from_step05(self):
        html_path = Path(__file__).resolve().parents[1] / "src/modules/search/out/yandex_market/html/step_05.html"
        if not html_path.is_file():
            pytest.skip("step_05.html capture missing")
        products = parse_yandex_html(html_path.read_text())
        assert len(products) == 24
        with_images = [product for product in products if product.image_link]
        assert len(with_images) >= 5
        for product in with_images[:5]:
            assert "get-mpic" in product.image_link
            assert product.image_link.endswith("/orig")
            assert product.image_link not in product.image_links
            assert "get-marketcms" not in product.image_link
        assert with_images[3].image_link != with_images[0].image_link

    @pytest.mark.asyncio
    async def test_collect_organic_only_on_sponsored_fixture(self):
        from playwright.async_api import async_playwright

        html = example_html("СПОНСОРСКИЕ Ноутбук Lenovo ThinkBook 16 — купить по низкой цене на Яндекс Маркете.html")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html, wait_until="domcontentloaded")
            all_snippets = await page.locator('[data-zone-name="productSnippet"]').count()
            products = await collect_products_from_page(page)
            await browser.close()

        assert all_snippets > len(products)
        assert len(products) >= 4

    @pytest.mark.asyncio
    async def test_collect_skips_sponsored_incut(self):
        from playwright.async_api import async_playwright

        from src.modules.search.yandex_market import _SPONSORED_INCUT_ZONE

        html = example_html("СПОНСОРСКИЕ Ноутбук Lenovo ThinkBook 16 — купить по низкой цене на Яндекс Маркете.html")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html, wait_until="domcontentloaded")
            sponsored_href = await page.evaluate(
                f"""() => {{
                  const snippet = document.querySelector(
                    '[data-zone-name="{_SPONSORED_INCUT_ZONE}"] [data-zone-name="productSnippet"] a[href*="/card/"]'
                  );
                  return snippet ? snippet.href : null;
                }}"""
            )
            products = await collect_products_from_page(page)
            await browser.close()

        assert sponsored_href
        assert len(products) >= 3
        collected_links = " ".join(product.product_link or "" for product in products)
        assert sponsored_href.split("?", 1)[0] not in collected_links


class TestWildberries:
    def test_product_card_specs(self):
        specs = parse_wb_detail_html(example_html("*Thinkbook*Wildberries*.html"))
        assert len(specs) >= 10
        assert specs.get("Артикул") == "676662119"
        assert specs.get("Модель") == "16 G8 IAL"
        assert specs.get("Серия ноутбуков") == "ThinkBook"

    def test_blocker_drawer_specs(self):
        specs = parse_wb_detail_html(example_html("blocker.html"))
        assert len(specs) >= 5
        assert specs.get("Цвет") == "черный"
        assert specs.get("Вид наушников") == "охватывающие"

    def test_card_api_options(self):
        payload = {
            "data": {
                "products": [
                    {
                        "id": 242056282,
                        "options": [
                            {"name": "Цвет", "value": "красный"},
                            {"name": "Длина намотки шнура (м)", "value": "10"},
                        ],
                    }
                ]
            }
        }
        specs = parse_wb_card_options(payload)
        assert specs.get("Артикул") == "242056282"
        assert specs.get("Цвет") == "красный"
        assert specs.get("Длина намотки шнура (м)") == "10"
        assert len(specs) >= 2

    def test_card_api_only_artikul_is_insufficient(self):
        specs = parse_wb_card_options({"data": {"products": [{"id": 242056282}]}})
        assert specs == {"Артикул": "242056282"}
        assert not _wb_specs_rich_enough(specs)

    def test_thinkbook_fixture_has_rich_specs(self):
        specs = parse_wb_detail_html(example_html("*Thinkbook*Wildberries*.html"))
        assert _wb_specs_rich_enough(specs)
        assert len(specs) >= 30

    def test_search_api_payload_legacy_price(self):
        payload = {
            "products": [
                {
                    "id": 676662119,
                    "name": "Ноутбук Thinkbook 16 G8",
                    "brand": "Lenovo",
                    "salePriceU": 7578400,
                    "rating": 5,
                    "feedbacks": 12,
                    "pics": 5,
                }
            ]
        }
        html = f'<pre id="d405f4e66468fd64bd88c8f16681286a">{json.dumps(payload, ensure_ascii=False)}</pre>'
        products = parse_wb_html(html)
        assert len(products) == 1
        assert "Lenovo" in products[0].name
        assert products[0].price == "75784"
        assert products[0].product_link.endswith("/676662119/detail.aspx")
        assert products[0].image_link == "https://basket-33.wbbasket.ru/vol6766/part676662/676662119/images/big/1.webp"
        assert len(products[0].image_links) == 4
        assert products[0].image_links[0].endswith("/2.webp")

    def test_search_api_payload_v18_sizes_price(self):
        payload = {
            "products": [
                {
                    "id": 725109772,
                    "brand": "Lenovo",
                    "name": 'Ноутбук ThinkBook 16 G7 ARP Ryzen7, 16 512GB, 16", Без ОС',
                    "wh": 300571,
                    "pics": 10,
                    "rating": 5,
                    "feedbacks": 5,
                    "sizes": [
                        {
                            "price": {
                                "basic": 9467000,
                                "product": 5296700,
                            }
                        }
                    ],
                }
            ]
        }
        html = f'<pre id="d405f4e66468fd64bd88c8f16681286a">{json.dumps(payload, ensure_ascii=False)}</pre>'
        product = parse_wb_html(html)[0]
        assert product.price == "52967"
        assert product.image_link == "https://basket-34.wbbasket.ru/vol7251/part725109/725109772/images/big/1.webp"

    def test_high_vol_nm_uses_basket_39(self):
        from src.modules.search.wildberries import _wb_image_url_for_index

        assert _wb_image_url_for_index(903747859, 1) == (
            "https://basket-39.wbbasket.ru/vol9037/part903747/903747859/images/big/1.webp"
        )

    def test_high_vol_nm_uses_basket_41(self):
        from src.modules.search.wildberries import _wb_image_url_for_index

        assert _wb_image_url_for_index(1030690898, 1) == (
            "https://basket-41.wbbasket.ru/vol10306/part1030690/1030690898/images/big/1.webp"
        )

    def test_card_image_from_html_overrides_basket_table(self):
        from src.modules.search.wildberries import _product_from_wb

        item = {"id": 1030690898, "name": "iPhone", "pics": 3}
        card_images = {
            "1030690898": ("https://basket-41.wbbasket.ru/vol10306/part1030690/1030690898/images/c516x688/1.webp"),
        }
        product = _product_from_wb(item, card_images=card_images)
        assert product is not None
        assert product.image_link.endswith("/images/big/1.webp")
        assert "basket-41" in product.image_link
        assert product.image_links[0].endswith("/images/big/2.webp")

    def test_scrape_card_images_from_search_html(self):
        from src.modules.search.wildberries import scrape_wb_card_images_from_html

        html = example_html(
            "ОПЕЧАТКА Интернет‑магазин Wildberries_ широкий ассортимент товаров - скидки каждый день!.html"
        )
        images = scrape_wb_card_images_from_html(html)
        assert images["178801948"].startswith("https://basket-12.wbbasket.ru/")
        assert "/images/c516x688/1.webp" in images["178801948"]

    def test_search_url_respects_spellcheck_flag(self):
        from src.modules.search.wildberries import _build_search_url

        query = "телефон ihone"
        assert "nocorrection=1" not in _build_search_url(query, spellcheck=True)
        no_correction = _build_search_url(query, spellcheck=False)
        assert "nocorrection=1" in no_correction
        assert "ihone" in no_correction

    def test_ozon_ihone_example(self):
        html = example_html("ОПЕЧАТКА телефон ihone - купить на OZON.html")
        assert parse_ozon_typofix(html) == "телефон iphone"

    def test_wildberries_ihone_example(self):
        html = example_html(
            "ОПЕЧАТКА Интернет‑магазин Wildberries_ широкий ассортимент товаров - скидки каждый день!.html"
        )
        assert parse_wildberries_typofix(html) == "телефон iphone"

    def test_yandex_market_ihone_example(self):
        html = example_html("ОПЕЧАТКА Телефон iphone — купить по низкой цене на Яндекс Маркете.html")
        assert parse_yandex_market_typofix(html, original="телефон ihone") == "телефон iphone"

    def test_yandex_search_text_json(self):
        html = example_html("ОПЕЧАТКА Телефон iphone — купить по низкой цене на Яндекс Маркете.html")
        assert parse_yandex_market_typofix(html, original="телефон ihone") == "телефон iphone"

    def test_wildberries_search_input(self):
        html = example_html(
            "ОПЕЧАТКА Интернет‑магазин Wildberries_ широкий ассортимент товаров - скидки каждый день!.html"
        )
        assert parse_wildberries_typofix(html, original="телефон ihone") == "телефон iphone"

    def test_ozon_typofix_merge_search_page_over_api(self):
        search_page = example_html("ОПЕЧАТКА телефон ihone - купить на OZON.html")
        api_page = Path("src/modules/search/out/ozon/html/step_04.html").read_text(errors="replace")
        original = "телефон ihone"
        merged = None
        for html in (search_page, api_page):
            merged = _merge_typofix_suggestion(
                merged,
                parse_ozon_typofix(html, original=original),
                original,
            )
        assert merged == "телефон iphone"

    def test_ozon_typofix_from_api_json(self):
        payload = {
            "shared": json.dumps(
                {
                    "catalog": {"correctedText": "телефон iphone"},
                },
                ensure_ascii=False,
            ),
            "widgetStates": {
                "searchBarDesktop-1": json.dumps(
                    {"text": "телефон iphone"},
                    ensure_ascii=False,
                ),
            },
        }
        html = f"<body>{json.dumps(payload, ensure_ascii=False)}</body>"
        assert parse_ozon_typofix(html) == "телефон iphone"

    def test_yandex_typofix_from_captured_pre(self):
        html = (
            '<pre id="typofix-suggestion">телефон iphone</pre>'
            '<pre id="d405f4e66468fd64bd88c8f16681286a">{"results":[]}</pre>'
        )
        assert parse_yandex_market_typofix(html) == "телефон iphone"


class TestOzon:
    def test_ozon_search_page_path_is_not_preencoded(self):
        from src.modules.search.ozon import _ozon_api_path, _ozon_search_page_path

        raw = _ozon_search_page_path("Ноутбук Lenovo ThinkBook 16")
        assert raw.startswith("/search/")
        assert raw == _ozon_search_page_path("Ноутбук Lenovo ThinkBook 16")
        assert "force_spell=true" in raw
        encoded = _ozon_api_path("Ноутбук Lenovo ThinkBook 16")
        assert encoded.startswith("%2Fsearch%2F")

    def test_ozon_search_page_path_respects_spellcheck_flag(self):
        from src.modules.search.ozon import _build_search_url, _ozon_search_page_path

        no_correction = _ozon_search_page_path("телефон ihone", spellcheck=False)
        assert "deny_category_prediction=true" in no_correction
        assert "force_spell=true" in no_correction
        assert "force_spell=false" not in no_correction

        with_correction = _ozon_search_page_path("телефон ihone", spellcheck=True)
        assert "deny_category_prediction=false" in with_correction
        assert "force_spell=true" in with_correction

        assert "force_spell" not in _build_search_url("телефон ihone", spellcheck=True)
        no_correction_url = _build_search_url("телефон ihone", spellcheck=False)
        assert "deny_category_prediction=true" in no_correction_url
        assert "force_spell=true" in no_correction_url

    def test_extract_next_page_path_from_search_api(self):
        from src.modules.search.ozon import _ozon_extract_next_page_path

        data = json.loads(
            (Path(__file__).resolve().parents[1] / "tests/example_htmls/ozon_search_api.json").read_text()
        )
        next_path = _ozon_extract_next_page_path(data)
        assert next_path
        assert next_path.startswith("/")
        assert "page=2" in next_path

    def test_merge_ozon_product_fills_missing_image_from_dom(self):
        from src.modules.search.ozon import _merge_ozon_product_lists
        from src.modules.search.schemas import SearchResult

        api_product = SearchResult(
            name="Apple iPhone 15",
            product_link="https://www.ozon.ru/product/apple-iphone-15-123/",
            price="50000",
        )
        dom_product = SearchResult(
            name="Apple iPhone 15",
            product_link="https://www.ozon.ru/product/apple-iphone-15-123/",
            image_link="https://ir.ozone.ru/s3/multimedia-1-a/123.jpg",
            image_links=["https://ir.ozone.ru/s3/multimedia-1-b/124.jpg"],
        )
        merged = _merge_ozon_product_lists([api_product], [dom_product])
        assert len(merged) == 1
        assert merged[0].image_link == dom_product.image_link
        assert merged[0].image_links == dom_product.image_links

    def test_search_api_response(self):
        html = example_html("ozon_search_api.html")
        products = parse_ozon_html(html)
        meta = fixture_json("ozon_fixtures_meta.json")
        assert len(products) == meta["search_products_count"]
        first = products[0]
        assert "ThinkBook" in first.name
        assert first.price
        assert first.product_link and "ozon.ru/product/" in first.product_link
        assert first.image_link and first.image_link.startswith("http")
        assert first.image_link not in first.image_links

    def test_detail_api_response(self):
        html = example_html("ozon_detail_api.html")
        specs = parse_ozon_detail_html(html)
        meta = fixture_json("ozon_fixtures_meta.json")
        assert len(specs) == meta["detail_specs_count"]
        assert len(specs) >= 10
        assert specs.get("Процессор") == "Intel Core Ultra 5 125U"
        assert specs.get("Общий объем SSD, ГБ") == "512"
        assert specs.get("Видеокарта") == "Intel Arc Graphics"
        assert specs.get("Артикул") == "3463205841"

    def test_detail_short_api_has_limited_specs(self):
        html = example_html("ozon_detail_short_api.html")
        specs = parse_ozon_detail_html(html)
        assert 1 <= len(specs) <= 5
