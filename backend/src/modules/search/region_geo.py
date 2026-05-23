"""Regional capitals → marketplace geo settings (see frontend/src/lib/regions.ts)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

# Capitals from frontend/src/lib/regions.ts (regionCapitalByName values).
REGION_CAPITALS: tuple[str, ...] = (
    "Барнаул",
    "Благовещенск",
    "Архангельск",
    "Астрахань",
    "Белгород",
    "Брянск",
    "Владимир",
    "Волгоград",
    "Вологда",
    "Воронеж",
    "Донецк",
    "Биробиджан",
    "Чита",
    "Запорожье",
    "Иваново",
    "Иркутск",
    "Нальчик",
    "Калининград",
    "Калуга",
    "Петропавловск-Камчатский",
    "Черкесск",
    "Кемерово",
    "Киров",
    "Кострома",
    "Краснодар",
    "Красноярск",
    "Курган",
    "Курск",
    "Гатчина",
    "Липецк",
    "Луганск",
    "Магадан",
    "Москва",
    "Красногорск",
    "Мурманск",
    "Нарьян-Мар",
    "Нижний Новгород",
    "Великий Новгород",
    "Новосибирск",
    "Омск",
    "Оренбург",
    "Орел",
    "Пенза",
    "Пермь",
    "Владивосток",
    "Псков",
    "Майкоп",
    "Горно-Алтайск",
    "Уфа",
    "Улан-Удэ",
    "Махачкала",
    "Магас",
    "Элиста",
    "Петрозаводск",
    "Сыктывкар",
    "Симферополь",
    "Йошкар-Ола",
    "Саранск",
    "Якутск",
    "Владикавказ",
    "Казань",
    "Кызыл",
    "Абакан",
    "Ростов-на-Дону",
    "Рязань",
    "Самара",
    "Санкт-Петербург",
    "Саратов",
    "Южно-Сахалинск",
    "Екатеринбург",
    "Севастополь",
    "Смоленск",
    "Ставрополь",
    "Тамбов",
    "Тверь",
    "Томск",
    "Тула",
    "Тюмень",
    "Ижевск",
    "Ульяновск",
    "Хабаровск",
    "Ханты-Мансийск",
    "Херсон",
    "Челябинск",
    "Грозный",
    "Чебоксары",
    "Анадырь",
    "Салехард",
    "Ярославль",
)

_OZON_SLUG_OVERRIDES: dict[str, str] = {
    "Санкт-Петербург": "sankt-peterburg",
    "Москва": "moskva",
    "Нижний Новгород": "nizhniy-novgorod",
    "Великий Новгород": "velikiy-novgorod",
    "Ростов-на-Дону": "rostov-na-donu",
    "Южно-Сахалинск": "yuzhno-sahalinsk",
    "Петропавловск-Камчатский": "petropavlovsk-kamchatskiy",
    "Йошкар-Ола": "yoshkar-ola",
    "Улан-Удэ": "ulan-ude",
    "Горно-Алтайск": "gorno-altaysk",
    "Нарьян-Мар": "naryan-mar",
    "Ханты-Мансийск": "hanty-mansiysk",
    "Республика Северная Осетия - Алания": "vladikavkaz",
}

_TRANSLIT: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

_DATA_PATH = Path(__file__).with_name("city_geo.json")
_YANDEX_REGION_RE = re.compile(r'"region"\s*:\s*\d+\b')
_WB_DEST_RE = re.compile(r"dest=(-?\d+)")


@dataclass(frozen=True, slots=True)
class CityGeo:
    city: str
    lat: float
    lon: float
    wb_dest: str
    yandex_lr: str
    ozon_slug: str | None = None
    ozon_pp: str | None = None


def normalize_city_name(city: str) -> str:
    return " ".join(city.strip().split())


def ozon_slug_for_city(city: str) -> str | None:
    city = normalize_city_name(city)
    if city in _OZON_SLUG_OVERRIDES:
        return _OZON_SLUG_OVERRIDES[city]
    if city not in REGION_CAPITALS:
        return None
    parts: list[str] = []
    for ch in city.lower():
        if ch in _TRANSLIT:
            parts.append(_TRANSLIT[ch])
        elif ch in " -":
            parts.append("-")
        elif ch.isalnum():
            parts.append(ch)
    slug = "".join(parts)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


@lru_cache(maxsize=1)
def _city_geo_index() -> dict[str, CityGeo]:
    if not _DATA_PATH.is_file():
        return {}
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    index: dict[str, CityGeo] = {}
    for entry in raw:
        geo = CityGeo(
            city=entry["city"],
            lat=float(entry["lat"]),
            lon=float(entry["lon"]),
            wb_dest=str(entry["wb_dest"]),
            yandex_lr=str(entry["yandex_lr"]),
            ozon_slug=entry.get("ozon_slug"),
            ozon_pp=entry.get("ozon_pp"),
        )
        index[normalize_city_name(geo.city)] = geo
    return index


def get_city_geo(city: str | None) -> CityGeo | None:
    if not city or not city.strip():
        return None
    return _city_geo_index().get(normalize_city_name(city))


def wb_geo_api_url(geo: CityGeo) -> str:
    return (
        "https://user-geo-data.wildberries.ru/get-geo-info"
        f"?latitude={geo.lat}&longitude={geo.lon}&address={quote(geo.city)}"
    )


@lru_cache(maxsize=128)
def wb_geo_json_for(geo: CityGeo) -> str:
    from urllib.request import urlopen

    with urlopen(wb_geo_api_url(geo), timeout=15) as response:
        return response.read().decode()


def make_wb_setup_page(geo: CityGeo):
    body = wb_geo_json_for(geo)

    async def _setup(page) -> None:
        async def _route_geo(route) -> None:
            if "get-geo-info" in route.request.url:
                await route.fulfill(status=200, content_type="application/json", body=body)
            else:
                await route.continue_()

        await page.route("**/*", _route_geo)

    return _setup


def make_yandex_setup_page(geo: CityGeo):
    target_lr = geo.yandex_lr

    def _patch(body: str) -> str:
        if not _YANDEX_REGION_RE.search(body):
            return body
        return _YANDEX_REGION_RE.sub(f'"region":{target_lr}', body)

    async def _setup(page) -> None:
        await page.context.grant_permissions(["geolocation"])
        await page.context.set_geolocation({"latitude": geo.lat, "longitude": geo.lon})

        async def _route_region(route) -> None:
            if "market.yandex.ru" not in route.request.url:
                await route.continue_()
                return
            if route.request.resource_type not in ("document", "xhr", "fetch"):
                await route.continue_()
                return
            try:
                response = await route.fetch()
                body = await response.text()
            except Exception:
                await route.continue_()
                return
            patched = _patch(body)
            if patched is body:
                await route.fulfill(response=response)
                return
            await route.fulfill(
                status=response.status,
                headers=response.headers,
                content_type=response.headers.get("content-type"),
                body=patched,
            )

        await page.route("**/*", _route_region)

    return _setup


def ozon_map_viewport_body(geo: CityGeo, *, delta: float = 0.02) -> str:
    payload = {
        "geolocation": {"coords": {}, "isAvailable": False},
        "form": {},
        "map": {
            "viewport": {
                "leftBottom": {
                    "latitude": geo.lat - delta,
                    "longitude": geo.lon - delta,
                },
                "rightTop": {
                    "latitude": geo.lat + delta,
                    "longitude": geo.lon + delta,
                },
            },
            "zoom": 17,
            "previousCoordinates": None,
        },
        "mapInfo": {
            "geoSessionId": "ac3d569a-3dd5-4e65-a5ea-d99b34577b6e",
            "preferredGeoProviders": {
                "suggest": ["maps_selfsuggest", "yandex"],
                "geocode": ["maps_selfsuggest", "yandex"],
                "revGeocode": ["maps_selfsuggest", "yandex"],
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def ozon_geo_url(geo: CityGeo) -> str | None:
    if not geo.ozon_slug:
        return None
    if geo.ozon_pp:
        return f"https://www.ozon.ru/geo/{geo.ozon_slug}/{geo.ozon_pp}/"
    return f"https://www.ozon.ru/geo/{geo.ozon_slug}/"


def ozon_pick_pvz_script(geo: CityGeo) -> str:
    slug = geo.ozon_slug or ""
    return f"""const slug = {json.dumps(slug)};
const re = new RegExp(`/geo/${{slug}}/(\\\\d+)/`);
const link = [...document.querySelectorAll('a[href]')].find((el) => {{
  try {{
    const path = new URL(el.href, location.origin).pathname;
    return re.test(path);
  }} catch (_) {{
    return false;
  }}
}});
if (link) {{
  link.click();
  return true;
}}
return false;"""
