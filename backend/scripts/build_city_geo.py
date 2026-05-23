#!/usr/bin/env -S uv run python
"""Build backend/src/modules/search/city_geo.json from REGION_CAPITALS."""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modules.search.region_geo import (  # noqa: E402
    _WB_DEST_RE,
    REGION_CAPITALS,
    ozon_slug_for_city,
)

OUT = ROOT / "src/modules/search/city_geo.json"
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


def main() -> None:
    entries: list[dict[str, object]] = []
    failed: list[str] = []

    for index, city in enumerate(REGION_CAPITALS, start=1):
        print(f"[{index}/{len(REGION_CAPITALS)}] {city}", flush=True)
        try:
            lat, lon = nominatim_coords(city)
            time.sleep(1.05)
            entry: dict[str, object] = {
                "city": city,
                "lat": lat,
                "lon": lon,
                "wb_dest": wb_dest(lat, lon, city),
                "yandex_lr": yandex_lr(city, lat, lon),
                "ozon_slug": ozon_slug_for_city(city),
            }
            entries.append(entry)
        except Exception as exc:
            print(f"  FAIL: {exc}", flush=True)
            failed.append(city)

    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} cities to {OUT}")
    if failed:
        print("Failed:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
