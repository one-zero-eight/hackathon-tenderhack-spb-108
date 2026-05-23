"""Shared Playwright block probe (plain Chromium, mirrors CloakBrowser flows)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Playwright, sync_playwright

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

_SCRIPTS_DIR = Path(__file__).resolve().parent


@dataclass
class StepResult:
    label: str
    elapsed_s: float
    url: str
    title: str
    captcha: bool
    products: int = 0
    specs: int = 0
    blocked: bool = False
    note: str = ""


@dataclass
class RoundResult:
    round_num: int
    elapsed_s: float
    blocked: bool
    captcha: bool
    products: int
    steps: list[StepResult] = field(default_factory=list)


@dataclass
class SiteProbe:
    site: str
    headless_env: str
    check_captcha: str
    default_query: str
    out_subdir: str
    parse_html: Callable[[str], list]
    run_search_flow: Callable[..., tuple[list[StepResult], bool]]
    parse_detail_html: Callable[[str], dict] | None = None
    run_detail_flow: Callable[..., tuple[list[StepResult], bool]] | None = None
    extra_blocked: Callable[[str, Page], bool] | None = None


@dataclass
class BrowserSession:
    playwright: Playwright
    context: Any
    page: Page
    browser: Any | None = None


def _ts() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def out_dir(probe: SiteProbe) -> Path:
    return _SCRIPTS_DIR / "out" / probe.out_subdir


def headless(probe: SiteProbe) -> bool:
    return os.environ.get(probe.headless_env, "0") == "1"


def captcha(page: Page, expr: str) -> bool:
    return bool(page.evaluate(f"() => Boolean({expr})"))


def page_title(page: Page) -> str:
    try:
        return (page.title() or "").strip()
    except Exception:
        return ""


def save_html(probe: SiteProbe, round_num: int, step: int, label: str, html: str) -> Path:
    directory = out_dir(probe)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"r{round_num:03d}_{step:02d}_{label}.html"
    path.write_text(html, encoding="utf-8")
    return path


def open_session(probe: SiteProbe, *, profile_dir: Path | None) -> BrowserSession:
    pw = sync_playwright().start()
    proxy_url = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    proxy = {"server": proxy_url} if proxy_url else None
    launch_kwargs: dict[str, Any] = {
        "headless": headless(probe),
        "locale": "ru-RU",
        "proxy": proxy,
    }
    if profile_dir is not None:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = pw.chromium.launch_persistent_context(
            str(profile_dir),
            viewport={"width": 1280, "height": 900},
            **launch_kwargs,
        )
        page = context.pages[0] if context.pages else context.new_page()
        return BrowserSession(playwright=pw, context=context, page=page)
    browser = pw.chromium.launch(headless=headless(probe))
    context = browser.new_context(
        locale="ru-RU",
        viewport={"width": 1280, "height": 900},
        proxy=proxy,
    )
    page = context.new_page()
    page.set_default_timeout(60_000)
    return BrowserSession(playwright=pw, context=context, page=page, browser=browser)


def close_session(session: BrowserSession) -> None:
    session.context.close()
    if session.browser is not None:
        session.browser.close()
    session.playwright.stop()


def goto(page: Page, url: str, wait_s: float) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    time.sleep(wait_s)


def run_async_js(page: Page, script_body: str) -> Any:
    return page.evaluate(f"async () => {{ {script_body} }}")


def run_sync_js(page: Page, script_body: str) -> Any:
    return page.evaluate(f"() => {{ {script_body} }}")


def wait_for_selector(page: Page, selector: str, *, timeout_s: float = 90) -> bool:
    try:
        page.wait_for_selector(selector, timeout=int(timeout_s * 1000))
        return True
    except Exception:
        return False


def inspect_step(
    probe: SiteProbe,
    page: Page,
    *,
    label: str,
    t0: float,
    round_num: int,
    step: int,
    count_products: bool = True,
    count_specs: bool = False,
) -> StepResult:
    html = page.content()
    path = save_html(probe, round_num, step, label, html)
    is_captcha = captcha(page, probe.check_captcha)
    products = len(probe.parse_html(html)) if count_products else 0
    specs = len(probe.parse_detail_html(html)) if count_specs and probe.parse_detail_html else 0
    blocked = is_captcha
    if probe.extra_blocked:
        blocked = blocked or probe.extra_blocked(html, page)
    note = f"saved {path.name}"
    if is_captcha:
        note += " | CAPTCHA"
    if blocked and not is_captcha:
        note += " | blocked"
    return StepResult(
        label=label,
        elapsed_s=time.perf_counter() - t0,
        url=page.url,
        title=page_title(page),
        captcha=is_captcha,
        products=products,
        specs=specs,
        blocked=blocked,
        note=note,
    )


def print_step(step: StepResult) -> None:
    extra: list[str] = []
    if step.products:
        extra.append(f"products={step.products}")
    if step.specs:
        extra.append(f"specs={step.specs}")
    if step.captcha:
        extra.append("CAPTCHA")
    if step.blocked:
        extra.append("BLOCKED")
    suffix = f" ({', '.join(extra)})" if extra else ""
    log(f"  {step.label} @ {step.elapsed_s:.1f}s | {step.title[:50]!r}{suffix} | {step.note}")


def run_round(
    probe: SiteProbe,
    page: Page,
    query: str,
    round_num: int,
    *,
    with_details: bool,
    product_link: str | None,
) -> RoundResult:
    t0 = time.perf_counter()
    steps, blocked = probe.run_search_flow(page, query, probe=probe, round_num=round_num, t0=t0)

    products = 0
    for step in steps:
        print_step(step)
        products = max(products, step.products)

    link = product_link
    if not blocked and with_details and probe.run_detail_flow:
        if not link and products:
            parsed = probe.parse_html(page.content())
            link = next((p.product_link for p in parsed if p.product_link), None)
        if link:
            detail_steps, detail_blocked = probe.run_detail_flow(page, link, probe=probe, round_num=round_num, t0=t0)
            steps.extend(detail_steps)
            blocked = blocked or detail_blocked
            for step in detail_steps:
                print_step(step)

    return RoundResult(
        round_num=round_num,
        elapsed_s=time.perf_counter() - t0,
        blocked=blocked,
        captcha=any(s.captcha for s in steps),
        products=products,
        steps=steps,
    )


def main(probe: SiteProbe, *, description: str) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--query", default=probe.default_query)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--new-browser-each-round", action="store_true")
    args = parser.parse_args()

    log(f"Site={probe.site} engine=playwright headless={headless(probe)} query={args.query!r}")
    log(f"Rounds={args.rounds} interval={args.interval}s details={args.details}")
    out_dir(probe).mkdir(parents=True, exist_ok=True)

    session_t0 = time.perf_counter()
    first_block_round: int | None = None
    product_link: str | None = None
    session: BrowserSession | None = None

    try:
        for round_num in range(1, args.rounds + 1):
            if session is None or args.new_browser_each_round:
                if session is not None:
                    close_session(session)
                log(f"--- Round {round_num}/{args.rounds}: starting Chromium (Playwright) ---")
                session = open_session(probe, profile_dir=args.profile)
            else:
                log(f"--- Round {round_num}/{args.rounds} ---")

            page = session.page
            result = run_round(
                probe,
                page,
                args.query,
                round_num,
                with_details=args.details,
                product_link=product_link,
            )

            if result.products and product_link is None:
                parsed = probe.parse_html(page.content())
                product_link = next((p.product_link for p in parsed if p.product_link), None)
                if product_link:
                    log(f"  pinned detail link: {product_link[:80]}...")

            status = "BLOCKED" if result.blocked else "ok"
            log(
                f"Round {round_num} done in {result.elapsed_s:.1f}s | "
                f"{status} | products={result.products} | "
                f"session {time.perf_counter() - session_t0:.1f}s"
            )

            if result.blocked and first_block_round is None:
                first_block_round = round_num
                log(
                    f"*** First block/captcha on round {round_num} "
                    f"after {time.perf_counter() - session_t0:.1f}s session time ***"
                )
                if not headless(probe):
                    log("Solve captcha in the browser window, or Ctrl+C to stop.")
                    try:
                        while captcha(page, probe.check_captcha):
                            time.sleep(2)
                        log("Captcha cleared — continuing probe.")
                        first_block_round = None
                        continue
                    except KeyboardInterrupt:
                        break
                break

            if round_num < args.rounds and args.interval > 0:
                time.sleep(args.interval)
    finally:
        if session is not None:
            close_session(session)

    summary = {
        "site": probe.site,
        "engine": "playwright",
        "query": args.query,
        "rounds_requested": args.rounds,
        "first_block_round": first_block_round,
        "session_seconds": round(time.perf_counter() - session_t0, 2),
        "headless": headless(probe),
        "new_browser_each_round": args.new_browser_each_round,
        "out_dir": str(out_dir(probe)),
    }
    summary_path = out_dir(probe) / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Summary: {summary_path}")
    if first_block_round is None:
        log(f"No block in {args.rounds} rounds ({summary['session_seconds']}s).")
        return 0
    log(f"Blocked on round {first_block_round} ({summary['session_seconds']}s).")
    return 1
