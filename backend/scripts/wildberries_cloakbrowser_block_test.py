"""Wildberries CloakBrowser block probe."""

from __future__ import annotations

import sys

from _cloakbrowser_block_probe import SiteProbe, StepResult, inspect_step, main

from src.modules.search.wildberries import (
    _DISMISS_BLOCKING_DRAWER_STMTS,
    CHECK_CAPTCHA,
    HEADLESS_ENV,
    SITE,
    _build_actions,
    parse_html,
    parse_wb_detail_html,
)

DEFAULT_QUERY = "Ноутбук Lenovo Thinkbook 16"


def _wb_labels(actions: list[dict[str, str]]) -> list[str]:
    labels: list[str] = []
    for action in actions:
        if action["type"] == "url":
            labels.append("search_page")
        elif action["type"] == "script":
            labels.append("dismiss_drawer")
        elif action["type"] == "waitElement" and "queryId" in action.get("wait_for", ""):
            labels.append("wait_query_id")
        elif action["type"] == "waitElement":
            labels.append("api_search")
        else:
            labels.append(action["type"])
    return labels


async def _run_detail_flow(
    probe: SiteProbe,
    page,
    product_link: str,
    *,
    round_num: int,
    t0: float,
) -> tuple[list[StepResult], bool]:
    await page.goto(product_link, wait_until="domcontentloaded", timeout=60_000)
    await page.evaluate(f"() => {{ {_DISMISS_BLOCKING_DRAWER_STMTS} }}")
    await page.wait_for_timeout(1000)
    step = await inspect_step(probe, page, label="detail_page", t0=t0, round_num=round_num, step=20)
    return [step], step.blocked


PROBE = SiteProbe(
    site=SITE,
    headless_env=HEADLESS_ENV,
    check_captcha=CHECK_CAPTCHA,
    default_query=DEFAULT_QUERY,
    out_subdir="wildberries-cloakbrowser-block",
    build_actions=_build_actions,
    parse_html=parse_html,
    parse_detail_html=parse_wb_detail_html,
    run_detail_flow=_run_detail_flow,
    action_labels=_wb_labels,
)

if __name__ == "__main__":
    sys.exit(main(PROBE, description="Wildberries CloakBrowser block probe"))
