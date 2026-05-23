"""Tests that Ozon applies region/geo during search setup."""

from src.modules.search.ozon import _build_actions as ozon_build_actions
from src.modules.search.region_geo import get_city_geo, ozon_geo_page_url

KAZAN = "Казань"
QUERY = "ноутбук"


def test_ozon_actions_include_geo_flow_for_kazan():
    geo = get_city_geo(KAZAN)
    geo_page = ozon_geo_page_url(geo)
    assert geo_page is not None

    actions = ozon_build_actions(QUERY, geo=geo)
    urls = [a["data"] for a in actions if a["type"] == "url"]
    assert geo_page in urls
    assert any("kazan" in u for u in urls)


def test_ozon_actions_skip_geo_flow_without_region():
    actions = ozon_build_actions(QUERY, geo=None)
    urls = [a["data"] for a in actions if a["type"] == "url"]
    assert not any("/geo/" in u for u in urls)
