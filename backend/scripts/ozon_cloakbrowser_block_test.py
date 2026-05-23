"""Ozon CloakBrowser block probe."""

from __future__ import annotations

import sys

from _cloakbrowser_block_probe import SiteProbe, StepResult, inspect_step, main

from src.modules.search.ozon import (
    CHECK_CAPTCHA,
    HEADLESS_ENV,
    SITE,
    _build_actions,
    _ozon_detail_api_url,
    _ozon_features_api_url,
    parse_html,
    parse_ozon_detail_html,
)

DEFAULT_QUERY = "Ноутбук Lenovo Thinkbook 16"


def _ozon_blocked(html: str, _page) -> bool:
    return "ограничен" in html.lower()[:8000]


def _ozon_labels(actions: list[dict[str, str]]) -> list[str]:
    labels: list[str] = []
    for action in actions:
        if action["type"] == "url" and "entrypoint-api" in action["data"]:
            labels.append("api_search")
        elif action["type"] == "url":
            labels.append("search_page")
        elif action["type"] == "waitElement":
            labels.append("geo_script")
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
    steps: list[StepResult] = []
    for idx, (label, url) in enumerate(
        (
            ("api_detail_features", _ozon_features_api_url(product_link)),
            ("api_detail_short", _ozon_detail_api_url(product_link)),
        ),
        start=10,
    ):
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(1500 if idx == 10 else 1000)
        step = await inspect_step(probe, page, label=label, t0=t0, round_num=round_num, step=idx)
        steps.append(step)
        if step.blocked:
            return steps, True
    return steps, False


PROBE = SiteProbe(
    site=SITE,
    headless_env=HEADLESS_ENV,
    check_captcha=CHECK_CAPTCHA,
    default_query=DEFAULT_QUERY,
    out_subdir="ozon-cloakbrowser-block",
    build_actions=_build_actions,
    parse_html=parse_html,
    parse_detail_html=parse_ozon_detail_html,
    run_detail_flow=_run_detail_flow,
    extra_blocked=_ozon_blocked,
    action_labels=_ozon_labels,
)

if __name__ == "__main__":
    sys.exit(main(PROBE, description="Ozon CloakBrowser block probe"))
