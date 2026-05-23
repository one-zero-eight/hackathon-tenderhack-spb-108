from src.modules.search.region_geo import REGION_CAPITALS, get_city_geo, ozon_slug_for_city


def test_all_capitals_in_city_geo_json():
    missing = [city for city in REGION_CAPITALS if get_city_geo(city) is None]
    assert not missing, f"missing geo: {missing[:5]}"


def test_get_city_geo_kazan():
    geo = get_city_geo("Казань")
    assert geo is not None
    assert geo.wb_dest == "-2133462"
    assert geo.yandex_lr == "43"
    assert geo.ozon_slug == "kazan"


def test_get_city_geo_none():
    assert get_city_geo(None) is None
    assert get_city_geo("") is None


def test_ozon_slug_moscow():
    assert ozon_slug_for_city("Москва") == "moskva"
