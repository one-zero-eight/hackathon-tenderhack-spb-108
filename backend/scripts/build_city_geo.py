#!/usr/bin/env -S uv run python
"""Build backend/src/modules/search/city_geo.json from REGION_CAPITALS."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modules.search.region_geo import (  # noqa: E402
    _OZON_BOOTSTRAP_URL,
    _WB_DEST_RE,
    REGION_CAPITALS,
    discover_ozon_pp_in_listing,
    ozon_slug_for_city,
)

OUT = ROOT / "src/modules/search/city_geo.json"
OZON_BUILD_PROFILE = ROOT / ".cache" / "ozon-geo-build"
USER_AGENT = "tenderhack-city-geo/1.0"


def fetch_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def nominatim_coords(city: str) -> tuple[float, float]:
    q = urllib.parse.quote(f"{city}, Russia")
    rows = fetch_json(f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1")
    if not rows:
        raise RuntimeError(f"no nominatim result for {city}")
    return float(rows[0]["lat"]), float(rows[0]["lon"])


def wb_dest(lat: float, lon: float, city: str) -> str:
    url = (
        "https://user-geo-data.wildberries.ru/get-geo-info"
        f"?latitude={lat}&longitude={lon}&address={urllib.parse.quote(city)}"
    )
    data = fetch_json(url)
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected wb response for {city}")
    xinfo = data.get("xinfo", "")
    match = _WB_DEST_RE.search(xinfo)
    if match:
        return match.group(1)
    destinations = data.get("destinations")
    if isinstance(destinations, list) and destinations:
        return str(destinations[-1])
    raise RuntimeError(f"no wb dest for {city}")


def yandex_lr(city: str, lat: float, lon: float) -> str:
    part = urllib.parse.quote(city)
    url = (
        "https://suggest-maps.yandex.ru/suggest-geo"
        f"?search_type=tune&v=9&results=1&lang=ru_RU&part={part}&ll={lon},{lat}"
    )
    data = fetch_json(url)
    results = data.get("results") if isinstance(data, dict) else None
    if not results:
        raise RuntimeError(f"no yandex lr for {city}")
    geoid = results[0].get("geoid")
    if geoid is None:
        raise RuntimeError(f"no geoid for {city}")
    return str(geoid)


def build_base_entries() -> tuple[list[dict[str, object]], list[str]]:
    entries: list[dict[str, object]] = []
    failed: list[str] = []

    for index, city in enumerate(REGION_CAPITALS, start=1):
        print(f"[{index}/{len(REGION_CAPITALS)}] {city}", flush=True)
        try:
            lat, lon = nominatim_coords(city)
            time.sleep(1.05)
            entries.append(
                {
                    "city": city,
                    "lat": lat,
                    "lon": lon,
                    "wb_dest": wb_dest(lat, lon, city),
                    "yandex_lr": yandex_lr(city, lat, lon),
                    "ozon_slug": ozon_slug_for_city(city),
                }
            )
        except Exception as exc:
            print(f"  FAIL: {exc}", flush=True)
            failed.append(city)

    return entries, failed


async def fetch_ozon_pp_by_slug(entries: list[dict[str, object]]) -> list[str]:
    from cloakbrowser import launch_persistent_context_async

    for entry in entries:
        city = str(entry["city"])
        entry["ozon_slug"] = ozon_slug_for_city(city)

    slug_to_cities: dict[str, list[str]] = {}
    for entry in entries:
        slug = entry.get("ozon_slug")
        if slug:
            slug_to_cities.setdefault(str(slug), []).append(str(entry["city"]))

    slugs = sorted(slug_to_cities)
    if not slugs:
        return []

    slug_to_pp: dict[str, str] = {}
    failed_slugs: list[str] = []

    OZON_BUILD_PROFILE.mkdir(parents=True, exist_ok=True)
    ctx = await launch_persistent_context_async(
        user_data_dir=str(OZON_BUILD_PROFILE),
        headless=True,
        locale="ru-RU",
    )
    page = await ctx.new_page()
    await page.goto(_OZON_BOOTSTRAP_URL, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(1000)

    async def listing_for(slug: str) -> str:
        return await page.evaluate(
            """async (slug) => {
              const r = await fetch(
                '/api/entrypoint-api.bx/page/json/v2?url=' + encodeURIComponent('/geo/' + slug + '/'),
                {credentials: 'include', headers: {accept: 'application/json'}}
              );
              return await r.text();
            }""",
            slug,
        )

    for index, slug in enumerate(slugs, start=1):
        print(f"  ozon_pp [{index}/{len(slugs)}] {slug}", flush=True)
        listing = await listing_for(slug)
        pp = discover_ozon_pp_in_listing(listing, slug)
        if not pp:
            await page.wait_for_timeout(1500)
            listing = await listing_for(slug)
            pp = discover_ozon_pp_in_listing(listing, slug)
        if pp:
            slug_to_pp[slug] = pp
            print(f"    -> {pp}", flush=True)
        else:
            print("    WARN: no pp in listing", flush=True)
            failed_slugs.append(slug)
        await page.wait_for_timeout(250)

    await ctx.close()

    for entry in entries:
        slug = entry.get("ozon_slug")
        if slug and slug in slug_to_pp:
            entry["ozon_pp"] = slug_to_pp[str(slug)]
        else:
            entry.pop("ozon_pp", None)

    return [c for slug in failed_slugs for c in slug_to_cities.get(slug, [])]


def write_entries(entries: list[dict[str, object]]) -> None:
    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} cities to {OUT}")


async def main_async(*, ozon_only: bool) -> None:
    if ozon_only:
        if not OUT.is_file():
            print(f"Missing {OUT} — run full build first", file=sys.stderr)
            sys.exit(1)
        entries = json.loads(OUT.read_text(encoding="utf-8"))
        print(f"Refreshing ozon_pp for {len(entries)} cities", flush=True)
    else:
        entries, failed = build_base_entries()
        if failed:
            print("Failed:", ", ".join(failed))
            sys.exit(1)

    failed_cities = await fetch_ozon_pp_by_slug(entries)
    write_entries(entries)
    if failed_cities:
        print("WARN: ozon_pp missing for:", ", ".join(failed_cities))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ozon-only",
        action="store_true",
        help="only refresh ozon_pp in existing city_geo.json (skip nominatim/wb/yandex)",
    )
    args = parser.parse_args()
    asyncio.run(main_async(ozon_only=args.ozon_only))


if __name__ == "__main__":
    main()
