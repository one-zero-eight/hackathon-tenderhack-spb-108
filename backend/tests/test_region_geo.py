from src.modules.search.region_geo import (
    REGION_CAPITALS,
    CityGeo,
    discover_ozon_pp_in_listing,
    geo_for_marketplace_search,
    get_city_geo,
    ozon_region_already_set_script,
    ozon_set_region_script,
    ozon_slug_for_city,
    remember_ozon_pp,
    resolve_ozon_pp,
    wb_region_already_set_script,
    yandex_region_already_set_script,
)


def test_all_capitals_in_city_geo_json():
    missing = [city for city in REGION_CAPITALS if get_city_geo(city) is None]
    assert not missing, f"missing geo: {missing[:5]}"


def test_most_capitals_have_ozon_pp_in_json():
    with_pp = sum(1 for city in REGION_CAPITALS if (g := get_city_geo(city)) and g.ozon_pp)
    assert with_pp >= 80, f"only {with_pp}/{len(REGION_CAPITALS)} have ozon_pp"


def test_get_city_geo_kazan():
    geo = get_city_geo("Казань")
    assert geo is not None
    assert geo.wb_dest == "-2133462"
    assert geo.yandex_lr == "43"
    assert geo.ozon_slug == "kazan"


def test_get_city_geo_none():
    assert get_city_geo(None) is None
    assert get_city_geo("") is None


def test_geo_for_marketplace_search_defaults_to_moscow():
    for region in (None, "", "   "):
        geo = geo_for_marketplace_search(region)
        assert geo is not None
        assert geo.city == "Москва"
        assert geo.wb_dest == "-535680"


def test_ozon_slug_moscow():
    assert ozon_slug_for_city("Москва") == "moskva"


def test_discover_ozon_pp_in_listing():
    text = '{"x":"/geo/kazan/357548/"}'
    assert discover_ozon_pp_in_listing(text, "kazan") == "357548"


def test_region_check_scripts_contain_target_geo():
    geo = get_city_geo("Новосибирск")
    assert geo is not None
    ozon_script = ozon_region_already_set_script(geo)
    assert geo.ozon_slug in ozon_script
    assert str(geo.ozon_pp) in ozon_set_region_script(geo)
    assert geo.wb_dest in wb_region_already_set_script(geo.wb_dest)
    assert geo.yandex_lr in yandex_region_already_set_script(geo)


def test_resolve_ozon_pp_runtime_cache():
    geo = get_city_geo("Казань")
    assert geo is not None
    remember_ozon_pp(geo.ozon_slug, "99999")
    without_json_pp = CityGeo(
        city=geo.city,
        lat=geo.lat,
        lon=geo.lon,
        wb_dest=geo.wb_dest,
        yandex_lr=geo.yandex_lr,
        ozon_slug=geo.ozon_slug,
        ozon_pp=None,
    )
    assert resolve_ozon_pp(without_json_pp) == "99999"
