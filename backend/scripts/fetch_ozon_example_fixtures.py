"""Fetch real Ozon API responses via CloakBrowser and save to tests/example_htmls."""

import asyncio
import json
import sys
from pathlib import Path

from cloakbrowser import launch_persistent_context_async

from src.modules.search.common import check_captcha, page_content, wait_captcha_solved
from src.modules.search.ozon import (
    CHECK_CAPTCHA,
    SITE,
    _build_actions,
    _ozon_detail_api_url,
    _ozon_features_api_url,
    _parse_ozon_json_html,
    parse_html,
    parse_ozon_detail_html,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "tests" / "example_htmls"
SESSION_DIR = EXAMPLES_DIR / ".ozon-fetch-session"
QUERY = "Ноутбук Lenovo Thinkbook 16"


async def _run_actions(page, actions: list[dict[str, str]]) -> None:
    for action in actions:
        action_type = action["type"]
        data = action["data"]
        if action_type == "url":
            await page.goto(data, wait_until="domcontentloaded", timeout=60_000)
        elif action_type == "wait":
            await page.wait_for_timeout(int(data))
        elif action_type == "waitElement":
            await page.evaluate(f"async () => {{ {data} }}")
        else:
            raise ValueError(action_type)
        if await check_captcha(page, CHECK_CAPTCHA, SITE):
            await wait_captcha_solved(page, CHECK_CAPTCHA)


def _save_api_capture(path: Path, html: str) -> dict | None:
    path.write_text(html, encoding="utf-8")
    data = _parse_ozon_json_html(html)
    if data:
        json_path = path.with_suffix(".json")
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  saved {path.name} + {json_path.name}")
    else:
        print(f"  saved {path.name} (JSON extract failed, raw html only)")
    return data


async def main() -> int:
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    context = await launch_persistent_context_async(
        user_data_dir=SESSION_DIR,
        headless=False,
        locale="ru-RU",
    )
    page = await context.new_page()

    try:
        print(f"Search query: {QUERY!r}")
        await _run_actions(page, _build_actions(QUERY))
        search_html = await page_content(page)
        search_data = _save_api_capture(EXAMPLES_DIR / "ozon_search_api.html", search_html)

        products = parse_html(search_html)
        print(f"Parsed {len(products)} products from search API")
        if not products:
            print("No products — check captcha or API response", file=sys.stderr)
            return 1

        product = next((p for p in products if p.product_link), products[0])
        print(f"Detail product: {product.name[:60]}")
        print(f"  link: {product.product_link}")

        features_url = _ozon_features_api_url(product.product_link)
        await page.goto(features_url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(1500)
        if await check_captcha(page, CHECK_CAPTCHA, SITE):
            await wait_captcha_solved(page, CHECK_CAPTCHA)
            await page.goto(features_url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(1500)

        detail_html = await page_content(page)
        detail_data = _save_api_capture(EXAMPLES_DIR / "ozon_detail_api.html", detail_html)
        specs = parse_ozon_detail_html(detail_html)

        detail_url = _ozon_detail_api_url(product.product_link)
        await page.goto(detail_url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(1000)
        _save_api_capture(EXAMPLES_DIR / "ozon_detail_short_api.html", await page_content(page))
        print(f"Parsed {len(specs)} characteristics from detail API")
        if specs:
            for key in list(specs)[:5]:
                print(f"  {key}: {specs[key][:50]}")

        meta = {
            "query": QUERY,
            "product_name": product.name,
            "product_link": product.product_link,
            "search_products_count": len(products),
            "detail_specs_count": len(specs),
            "search_has_widget_states": bool(search_data and search_data.get("widgetStates")),
            "detail_has_widget_states": bool(detail_data and detail_data.get("widgetStates")),
        }
        (EXAMPLES_DIR / "ozon_fixtures_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("Done.")
        return 0
    finally:
        await page.close()
        await context.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
