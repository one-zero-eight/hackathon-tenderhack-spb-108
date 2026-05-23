"""Ozon Playwright block probe — same flow as CloakBrowser parser.

Run from backend/:
  uv run --with playwright scripts/ozon_playwright_block_test.py
  OZON_HEADLESS=1 uv run --with playwright scripts/ozon_playwright_block_test.py --rounds 5
"""

from __future__ import annotations

import json
import sys
import time

from _playwright_block_probe import (
    SiteProbe,
    StepResult,
    captcha,
    goto,
    inspect_step,
    main,
    page_title,
    run_async_js,
)

from src.modules.search.ozon import (
    _GEO_SCRIPT_TEMPLATE,
    CHECK_CAPTCHA,
    HEADLESS_ENV,
    SITE,
    _build_search_url,
    _ozon_detail_api_url,
    _ozon_features_api_url,
    _search_api_url,
    parse_html,
    parse_ozon_detail_html,
)

DEFAULT_QUERY = "Ноутбук Lenovo Thinkbook 16"


def _ozon_blocked(html: str, _page) -> bool:
    return "ограничен" in html.lower()[:8000]


def _geo_script() -> str:
    return _GEO_SCRIPT_TEMPLATE.replace("__CITY_INFO__", json.dumps(""))


def _run_search_flow(
    page,
    query: str,
    *,
    probe: SiteProbe,
    round_num: int,
    t0: float,
) -> tuple[list[StepResult], bool]:
    steps: list[StepResult] = []

    goto(page, _build_search_url(query), 5.0)
    step = inspect_step(probe, page, label="search_page", t0=t0, round_num=round_num, step=1, count_products=False)
    steps.append(step)
    if step.blocked:
        return steps, True

    run_async_js(page, _geo_script())
    time.sleep(0.5)
    step = StepResult(
        label="geo_script",
        elapsed_s=time.perf_counter() - t0,
        url=page.url,
        title=page_title(page),
        captcha=captcha(page, probe.check_captcha),
        note="geo POST executed",
    )
    if step.captcha:
        step.blocked = True
        steps.append(step)
        return steps, True
    steps.append(step)

    goto(page, _search_api_url(query), 3.0)
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
    steps: list[StepResult] = []
    for idx, (label, url) in enumerate(
        (
            ("api_detail_features", _ozon_features_api_url(product_link)),
            ("api_detail_short", _ozon_detail_api_url(product_link)),
        ),
        start=4,
    ):
        goto(page, url, 1.5 if idx == 4 else 1.0)
        step = inspect_step(
            probe,
            page,
            label=label,
            t0=t0,
            round_num=round_num,
            step=idx,
            count_products=False,
            count_specs=True,
        )
        steps.append(step)
        if step.blocked:
            return steps, True
    return steps, False


PROBE = SiteProbe(
    site=SITE,
    headless_env=HEADLESS_ENV,
    check_captcha=CHECK_CAPTCHA,
    default_query=DEFAULT_QUERY,
    out_subdir="ozon-playwright-block",
    parse_html=parse_html,
    parse_detail_html=parse_ozon_detail_html,
    run_search_flow=_run_search_flow,
    run_detail_flow=_run_detail_flow,
    extra_blocked=_ozon_blocked,
)

if __name__ == "__main__":
    sys.exit(main(PROBE, description="Ozon Playwright block probe (mirrors CloakBrowser flow)"))
