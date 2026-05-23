"""Yandex Market CloakBrowser block probe."""

from __future__ import annotations

import sys

from _cloakbrowser_block_probe import SiteProbe, StepResult, inspect_step, main

from src.modules.search.yandex_market import (
    CHECK_CAPTCHA,
    HEADLESS_ENV,
    SITE,
    _build_actions,
    parse_html,
    parse_yandex_detail_html,
)

DEFAULT_QUERY = "Ноутбук Lenovo Thinkbook 16"


def _yandex_blocked(html: str, page) -> bool:
    return "showcaptcha" in page.url.lower() or "<title>403</title>" in html or "blocked" in html.lower()[:5000]


def _yandex_labels(actions: list[dict[str, str]]) -> list[str]:
    labels: list[str] = []
    for action in actions:
        if action["type"] == "url" and action["data"].rstrip("/").endswith("market.yandex.ru"):
            labels.append("home")
        elif action["type"] == "url":
            labels.append("search_page")
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
    try:
        await page.wait_for_selector('[data-auto="product-spec"]', timeout=5_000)
    except Exception:
        pass
    step = await inspect_step(probe, page, label="detail_page", t0=t0, round_num=round_num, step=20)
    return [step], step.blocked


PROBE = SiteProbe(
    site=SITE,
    headless_env=HEADLESS_ENV,
    check_captcha=CHECK_CAPTCHA,
    default_query=DEFAULT_QUERY,
    out_subdir="yandex-market-cloakbrowser-block",
    build_actions=_build_actions,
    parse_html=parse_html,
    parse_detail_html=parse_yandex_detail_html,
    run_detail_flow=_run_detail_flow,
    extra_blocked=_yandex_blocked,
    action_labels=_yandex_labels,
)

if __name__ == "__main__":
    sys.exit(main(PROBE, description="Yandex Market CloakBrowser block probe"))
