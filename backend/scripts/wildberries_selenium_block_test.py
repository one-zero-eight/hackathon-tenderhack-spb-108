"""Wildberries Selenium block probe — same flow as CloakBrowser parser.

Run from backend/:
  uv run --with selenium scripts/wildberries_selenium_block_test.py
  WILDBERRIES_HEADLESS=1 uv run --with selenium scripts/wildberries_selenium_block_test.py --rounds 5
"""

from __future__ import annotations

import sys
import time
from urllib.parse import quote

from _selenium_block_probe import (
    SiteProbe,
    StepResult,
    goto,
    inspect_step,
    main,
    run_async_js,
    run_sync_js,
    wait_for_selector,
)

from src.modules.search.common import RESULT_PRE_ID
from src.modules.search.wildberries import (
    _DISMISS_BLOCKING_DRAWER_STMTS,
    _WAIT_FETCH_TEMPLATE,
    _WAIT_QUERY_ID,
    CHECK_CAPTCHA,
    DEST,
    HEADLESS_ENV,
    SITE,
    _build_search_url,
    _wb_price_filter_js,
    parse_html,
    parse_wb_detail_html,
)

DEFAULT_QUERY = "Ноутбук Lenovo Thinkbook 16"


def _fetch_script(query: str) -> str:
    return (
        _WAIT_FETCH_TEMPLATE.replace("__PRE_ID__", RESULT_PRE_ID)
        .replace("__DEST__", DEST)
        .replace("__QUERY_ENC__", quote(query))
        .replace("__PRICE_FILTER_JS__", _wb_price_filter_js())
    )


def _run_search_flow(
    driver,
    query: str,
    *,
    probe: SiteProbe,
    round_num: int,
    t0: float,
) -> tuple[list[StepResult], bool]:
    steps: list[StepResult] = []

    goto(driver, _build_search_url(query), 5.0)
    step = inspect_step(probe, driver, label="search_page", t0=t0, round_num=round_num, step=1, count_products=False)
    steps.append(step)
    if step.blocked:
        return steps, True

    run_sync_js(driver, _DISMISS_BLOCKING_DRAWER_STMTS)
    time.sleep(0.5)

    run_async_js(driver, _WAIT_QUERY_ID)
    if not wait_for_selector(driver, "pre#queryId", timeout_s=25):
        step = inspect_step(
            probe,
            driver,
            label="wait_query_id",
            t0=t0,
            round_num=round_num,
            step=2,
            count_products=False,
        )
        step.blocked = True
        step.note += " | queryId timeout"
        steps.append(step)
        return steps, True

    time.sleep(5.0)

    run_async_js(driver, _fetch_script(query))
    if not wait_for_selector(driver, f"pre#{RESULT_PRE_ID}", timeout_s=30):
        step = inspect_step(
            probe,
            driver,
            label="api_fetch",
            t0=t0,
            round_num=round_num,
            step=3,
        )
        step.blocked = step.blocked or step.products == 0
        if step.products == 0:
            step.note += " | pre timeout/empty"
        steps.append(step)
        return steps, step.blocked

    step = inspect_step(probe, driver, label="api_search", t0=t0, round_num=round_num, step=3)
    steps.append(step)
    return steps, step.blocked


def _run_detail_flow(
    driver,
    product_link: str,
    *,
    probe: SiteProbe,
    round_num: int,
    t0: float,
) -> tuple[list[StepResult], bool]:
    from _selenium_block_probe import goto as _goto

    _goto(driver, product_link, 3.0)
    run_sync_js(driver, _DISMISS_BLOCKING_DRAWER_STMTS)
    time.sleep(1.0)
    step = inspect_step(
        probe,
        driver,
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
    out_subdir="wildberries-selenium-block",
    parse_html=parse_html,
    parse_detail_html=parse_wb_detail_html,
    run_search_flow=_run_search_flow,
    run_detail_flow=_run_detail_flow,
)

if __name__ == "__main__":
    sys.exit(
        main(
            PROBE,
            description="Wildberries Selenium block probe (mirrors CloakBrowser flow)",
        )
    )
