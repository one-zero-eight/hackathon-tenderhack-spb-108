import json
from pathlib import Path

from src.modules.search.common import RESULT_PRE_ID, _merge_typofix_suggestion, normalize_display_text
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
from src.modules.search.yandex_market import parse_html as parse_yandex_html
from src.modules.search.yandex_market import parse_yandex_detail_html
from tests.conftest import example_html, fixture_json


class TestYandexMarket:
    def test_normalize_display_text_decodes_double_encoded_entities(self):
        assert normalize_display_text("16&amp;quot; Laptop") == '16" Laptop'
        assert normalize_display_text("foo&nbsp;bar") == "foo bar"

    def test_dom_products_payload_unescapes_names(self):
        payload = json.dumps(
            {
                "__domProducts": [
                    {
                        "name": "16&amp;quot; Ноутбук Lenovo Thinkbook 16",
                        "product_link": "https://market.yandex.ru/card/test/123",
                        "price": "7350",
                    }
                ]
            }
        )
        html = f'<pre id="{RESULT_PRE_ID}">{payload}</pre>'
        products = parse_yandex_html(html)
        assert len(products) == 1
        assert products[0].name == '16" Ноутбук Lenovo Thinkbook 16'

    def test_product_card_specs(self):
        specs = parse_yandex_detail_html(example_html("16_*ин.html"))
        assert len(specs) >= 10
        assert specs.get("Артикул Маркета") == "4926170907"
        assert specs.get("Бренд") == "Lenovo"
        assert "Диагональ экрана" in specs

    def test_search_page_has_product_snippets(self):
        html = example_html("Ноутбук Lenovo Thinkbook 16 — купить по низкой цене на Яндекс Маркете.html")
        assert 'data-zone-name="productSnippet"' in html


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


class TestTypofix:
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
