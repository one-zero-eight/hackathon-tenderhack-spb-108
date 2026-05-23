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
    "Благовещенск": "blagoveshchensk",
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
_OZON_BOOTSTRAP_URL = "https://www.ozon.ru/"
_YANDEX_REGION_RE = re.compile(r'"region"\s*:\s*\d+\b')
# Default delivery-point ids in a fresh Market session (Moscow / SPb).
_YANDEX_DEFAULT_DELIVERY_IDS = ("213", "2")
_WB_DEST_RE = re.compile(r"dest=(-?\d+)")
_RUNTIME_OZON_PP: dict[str, str] = {}


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


@lru_cache(maxsize=1)
def _ozon_pp_by_slug_from_json() -> dict[str, str]:
    by_slug: dict[str, str] = {}
    for geo in _city_geo_index().values():
        if geo.ozon_slug and geo.ozon_pp:
            by_slug[geo.ozon_slug] = geo.ozon_pp
    return by_slug


def discover_ozon_pp_in_listing(listing_text: str, slug: str) -> str | None:
    match = re.search(rf"/geo/{re.escape(slug)}/(\d{{5,8}})/", listing_text)
    return match.group(1) if match else None


def remember_ozon_pp(slug: str, pp: str) -> None:
    _RUNTIME_OZON_PP[slug] = pp


def resolve_ozon_pp(geo: CityGeo) -> str | None:
    slug = geo.ozon_slug
    if not slug:
        return None
    if geo.ozon_pp:
        return geo.ozon_pp
    cached = _RUNTIME_OZON_PP.get(slug)
    if cached:
        return cached
    return _ozon_pp_by_slug_from_json().get(slug)


async def cache_ozon_pp_on_page(page, geo: CityGeo) -> None:
    slug = geo.ozon_slug
    if not slug or resolve_ozon_pp(geo):
        return
    if "ozon.ru" not in page.url:
        await page.goto(_OZON_BOOTSTRAP_URL, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(500)
    listing = await page.evaluate(
        """async (slug) => {
          const r = await fetch(
            '/api/entrypoint-api.bx/page/json/v2?url=' + encodeURIComponent('/geo/' + slug + '/'),
            {credentials: 'include', headers: {accept: 'application/json'}}
          );
          return await r.text();
        }""",
        slug,
    )
    pp = discover_ozon_pp_in_listing(listing, slug)
    if pp:
        remember_ozon_pp(slug, pp)


def make_ozon_setup_page(geo: CityGeo):
    async def _setup(page) -> None:
        await cache_ozon_pp_on_page(page, geo)

    return _setup


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


def _region_check_eval_body(fn_def: str, fn_name: str) -> str:
    return f"{fn_def}\nreturn {fn_name}();"


def make_wb_setup_page(geo: CityGeo):
    body = wb_geo_json_for(geo)
    check_body = _region_check_eval_body(
        wb_region_already_set_script(geo.wb_dest),
        "wbRegionAlreadySet",
    )

    async def _setup(page) -> None:
        url = page.url or ""
        if url.startswith("http") and "wildberries" in url:
            try:
                if await page.evaluate(f"() => {{ {check_body} }}"):
                    return
            except Exception:
                pass

        async def _route_geo(route) -> None:
            if "get-geo-info" in route.request.url:
                await route.fulfill(status=200, content_type="application/json", body=body)
            else:
                await route.continue_()

        await page.route("**/*", _route_geo)

    return _setup


def ozon_geo_page_url(geo: CityGeo) -> str | None:
    slug = geo.ozon_slug
    pp = resolve_ozon_pp(geo)
    if not slug or not pp:
        return None
    return f"{_OZON_BOOTSTRAP_URL}geo/{slug}/{pp}/"


def make_yandex_setup_page(geo: CityGeo):
    target_lr = geo.yandex_lr
    target_city = geo.city

    def _already_target_region(body: str) -> bool:
        if f'"region":{target_lr}' not in body:
            return False
        if f">{target_city}</span>" in body:
            return True
        return f'"id":"{target_lr}","regionId":{target_lr}' in body or f'"deliveryPointId":{target_lr}' in body

    def _patch(body: str) -> str:
        if _already_target_region(body):
            return body
        if _YANDEX_REGION_RE.search(body):
            body = _YANDEX_REGION_RE.sub(f'"region":{target_lr}', body)
        for old_id in _YANDEX_DEFAULT_DELIVERY_IDS:
            body = body.replace(
                f'"id":"{old_id}","regionId":{old_id}',
                f'"id":"{target_lr}","regionId":{target_lr}',
            )
            body = body.replace(f'"deliveryPointId":{old_id}', f'"deliveryPointId":{target_lr}')
        body = body.replace(f">{target_city}</span>", ">__TMP_CITY__</span>")
        body = body.replace(">Москва</span>", f">{target_city}</span>")
        body = body.replace(">Санкт-Петербург</span>", f">{target_city}</span>")
        body = body.replace(">__TMP_CITY__</span>", f">{target_city}</span>")
        return body

    async def _setup(page) -> None:
        skip_route = False
        if page.url and "market.yandex.ru" in page.url:
            check_body = _region_check_eval_body(
                yandex_region_already_set_script(geo),
                "yandexRegionAlreadySet",
            )
            skip_route = await page.evaluate(f"() => {{ {check_body} }}")

        if not skip_route:
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
            if _already_target_region(body):
                await route.fulfill(response=response)
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

        if not skip_route:
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


def ozon_region_already_set_check(geo: CityGeo) -> str:
    return _region_check_eval_body(ozon_region_already_set_script(geo), "ozonRegionAlreadySet")


def ozon_region_already_set_script(geo: CityGeo) -> str:
    slug = json.dumps(geo.ozon_slug or "")
    pp = json.dumps(resolve_ozon_pp(geo))
    city = json.dumps(geo.city)
    return f"""function ozonRegionAlreadySet() {{
  const city = {city};
  const slug = {slug};
  const pp = {pp};
  if (!pp) return false;
  if (location.pathname.includes('/geo/' + slug + '/' + pp)) return true;
  const header = document.querySelector('header');
  if (header && header.innerText.includes(city)) return true;
  const addr = document.querySelector('[data-widget="addressBookBar"]');
  if (addr && addr.innerText.includes(city)) return true;
  return false;
}}"""


def ozon_set_region_script(geo: CityGeo) -> str:
    """Set Ozon delivery point via entrypoint API only (no map UI)."""
    slug = geo.ozon_slug or ""
    pp = resolve_ozon_pp(geo)
    pp_json = json.dumps(pp) if pp else "null"
    map_body = ozon_map_viewport_body(geo)
    return f"""{ozon_region_already_set_script(geo)}
if (ozonRegionAlreadySet()) return true;
const slug = {json.dumps(slug)};
const pp = {pp_json};
const mapBody = {map_body};
if (!pp) return false;
const geoUrl =
  '/api/entrypoint-api.bx/page/json/v2?url=' +
  encodeURIComponent('/geo/' + slug + '/?azimuth=0&nfr=t&pid=7&pp=' + pp);
const geoR = await fetch(geoUrl, {{
  method: 'POST',
  headers: {{'content-type': 'application/json', accept: 'application/json'}},
  body: mapBody,
  credentials: 'include',
}});
return geoR.ok;"""


def ozon_confirm_region_script(geo: CityGeo) -> str:
    """Confirm Ozon delivery point in the header (updates visible region)."""
    return f"""{ozon_region_already_set_script(geo)}
if (ozonRegionAlreadySet()) return true;
const labels = ['Сохранить адрес', 'Сохранить', 'Продолжить'];
for (const label of labels) {{
  const btn = [...document.querySelectorAll('button')].find(
    (b) => b.innerText && b.innerText.includes(label)
  );
  if (btn) {{
    btn.click();
    return true;
  }}
}}
return false;"""


def wb_region_already_set_script(wb_dest: str) -> str:
    target = json.dumps(wb_dest)
    return f"""function wbRegionAlreadySet() {{
  const target = {target};
  try {{
    const cookieMatch = document.cookie.match(/(?:^|;\\s*)dest=(-?\\d+)/);
    if (cookieMatch && cookieMatch[1] === target) return true;
  }} catch (_) {{}}
  try {{
    const urlDest = new URLSearchParams(location.search).get('dest');
    if (urlDest === target) return true;
  }} catch (_) {{}}
  return false;
}}"""


def yandex_region_already_set_script(geo: CityGeo) -> str:
    city = json.dumps(geo.city)
    lr = json.dumps(geo.yandex_lr)
    return f"""function yandexRegionAlreadySet() {{
  const city = {city};
  const lr = {lr};
  const urlLr = new URL(location.href).searchParams.get('lr');
  if (urlLr === lr) {{
    const dp = document.querySelector('[data-zone-name="deliveryPoint"]');
    if (dp) {{
      try {{
        const data = JSON.parse(dp.getAttribute('data-zone-data') || '{{}}');
        if (String(data.regionId) === lr || String(data.id) === lr) return true;
      }} catch (_) {{}}
    }}
    const anchor = document.querySelector('#hyperlocation-unified-dialog-anchor');
    if (anchor) {{
      for (const span of anchor.querySelectorAll('span')) {{
        if (span.textContent.trim() === city) return true;
      }}
    }}
  }}
  const dp = document.querySelector('[data-zone-name="deliveryPoint"]');
  if (dp) {{
    try {{
      const data = JSON.parse(dp.getAttribute('data-zone-data') || '{{}}');
      if (String(data.regionId) === lr || String(data.id) === lr) return true;
    }} catch (_) {{}}
  }}
  const anchor = document.querySelector('#hyperlocation-unified-dialog-anchor');
  if (anchor) {{
    for (const span of anchor.querySelectorAll('span')) {{
      if (span.textContent.trim() === city) return true;
    }}
  }}
  return false;
}}"""


def yandex_sync_region_ui_script(geo: CityGeo) -> str:
    """Sync Market header delivery widget with the target city (visible region)."""
    city = json.dumps(geo.city)
    lr = geo.yandex_lr
    return f"""{yandex_region_already_set_script(geo)}
if (yandexRegionAlreadySet()) return true;
const city = {city};
const lr = {lr};
const dp = document.querySelector('[data-zone-name="deliveryPoint"]');
if (dp) {{
  try {{
    const data = JSON.parse(dp.getAttribute('data-zone-data') || '{{}}');
    data.id = String(lr);
    data.regionId = Number(lr);
    dp.setAttribute('data-zone-data', JSON.stringify(data));
  }} catch (_) {{}}
}}
const anchor = document.querySelector('#hyperlocation-unified-dialog-anchor');
if (anchor) {{
  for (const span of anchor.querySelectorAll('span')) {{
    const t = span.textContent.trim();
    if (t === 'Москва' || t === 'Санкт-Петербург') span.textContent = city;
  }}
}}
return true;"""
