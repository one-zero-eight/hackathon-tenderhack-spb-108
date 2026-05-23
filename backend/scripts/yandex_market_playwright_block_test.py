"""Yandex Market Playwright block probe — same flow as CloakBrowser parser.

Run from backend/:
  uv run --with playwright scripts/yandex_market_playwright_block_test.py
  YANDEX_MARKET_HEADLESS=1 uv run --with playwright scripts/yandex_market_playwright_block_test.py
"""

from __future__ import annotations

import json
import sys

from _playwright_block_probe import (
    SiteProbe,
    StepResult,
    goto,
    inspect_step,
    main,
    run_async_js,
    wait_for_selector,
)

from src.modules.search.common import DEFAULT_MAX_PRICE, DEFAULT_MIN_PRICE, RESULT_PRE_ID
from src.modules.search.yandex_market import (
    _WAIT_ELEMENT_TEMPLATE,
    CHECK_CAPTCHA,
    HEADLESS_ENV,
    SITE,
    _build_search_url,
    parse_html,
    parse_yandex_detail_html,
)

DEFAULT_QUERY = "Ноутбук Lenovo Thinkbook 16"
_YANDEX_HOME = "https://market.yandex.ru"


def _resolve_script(query: str) -> str:
    return (
        _WAIT_ELEMENT_TEMPLATE.replace("__SEARCH_TEXT__", json.dumps(query))
        .replace("__PRE_ID__", RESULT_PRE_ID)
        .replace("__MIN_PRICE__", str(DEFAULT_MIN_PRICE))
        .replace("__MAX_PRICE__", str(DEFAULT_MAX_PRICE))
    )


def _yandex_blocked(html: str, page) -> bool:
    title = (page.title() or "").strip()
    return "showcaptcha" in page.url.lower() or title == "403" or "blocked" in html.lower()[:5000]


def _run_search_flow(
    page,
    query: str,
    *,
    probe: SiteProbe,
    round_num: int,
    t0: float,
) -> tuple[list[StepResult], bool]:
    steps: list[StepResult] = []

    goto(page, _YANDEX_HOME, 1.0)
    step = inspect_step(probe, page, label="home", t0=t0, round_num=round_num, step=1, count_products=False)
    steps.append(step)
    if step.blocked:
        return steps, True

    goto(page, _build_search_url(query), 1.5)
    step = inspect_step(probe, page, label="search_page", t0=t0, round_num=round_num, step=2, count_products=False)
    steps.append(step)
    if step.blocked:
        return steps, True

    run_async_js(page, _resolve_script(query))
    if not wait_for_selector(page, f"pre#{RESULT_PRE_ID}", timeout_s=60):
        step = inspect_step(probe, page, label="api_resolve", t0=t0, round_num=round_num, step=3)
        step.blocked = step.blocked or step.products == 0
        if step.products == 0:
            step.note += " | pre timeout/empty"
        steps.append(step)
        return steps, step.blocked

    step = inspect_step(probe, page, label="api_search", t0=t0, round_num=round_num, step=3)
    steps.append(step)
    return steps, step.blocked


def _run_detail_flow(
    page,
    product_link: str,
    *,
    probe: SiteProbe,
    round_num: int,
    t0: float,
) -> tuple[list[StepResult], bool]:
    goto(page, product_link, 3.0)
    wait_for_selector(page, '[data-auto="product-spec"]', timeout_s=8)
    step = inspect_step(
        probe,
        page,
        label="detail_page",
        t0=t0,
        round_num=round_num,
        step=4,
        count_products=False,
        count_specs=True,
    )
    return [step], step.blocked


PROBE = SiteProbe(
    site=SITE,
    headless_env=HEADLESS_ENV,
    check_captcha=CHECK_CAPTCHA,
    default_query=DEFAULT_QUERY,
    out_subdir="yandex-market-playwright-block",
    parse_html=parse_html,
    parse_detail_html=parse_yandex_detail_html,
    run_search_flow=_run_search_flow,
    run_detail_flow=_run_detail_flow,
    extra_blocked=_yandex_blocked,
)

if __name__ == "__main__":
    sys.exit(
        main(
            PROBE,
            description="Yandex Market Playwright block probe (mirrors CloakBrowser flow)",
        )
    )
