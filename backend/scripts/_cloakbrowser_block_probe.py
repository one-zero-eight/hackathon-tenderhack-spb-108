"""Shared CloakBrowser block probe (same flows as production parsers)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cloakbrowser import launch_persistent_context_async

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.modules.search.common import RESULT_PRE_ID, page_content  # noqa: E402

_SCRIPTS_DIR = Path(__file__).resolve().parent
HTTP_PROXY: str | None = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")


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
class SiteProbe:
    site: str
    headless_env: str
    check_captcha: str
    default_query: str
    out_subdir: str
    build_actions: Callable[..., list[dict[str, str]]]
    parse_html: Callable[[str], list]
    parse_detail_html: Callable[[str], dict] | None = None
    run_detail_flow: Callable[..., Any] | None = None
    extra_blocked: Callable[[str, Any], bool] | None = None
    action_labels: Callable[[list[dict[str, str]]], list[str]] | None = None


def _ts() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def out_dir(probe: SiteProbe) -> Path:
    return _SCRIPTS_DIR / "out" / probe.out_subdir


def session_dir(probe: SiteProbe) -> Path:
    return out_dir(probe) / "session"


def headless(probe: SiteProbe) -> bool:
    return os.environ.get(probe.headless_env, "0") == "1"


async def captcha(page, expr: str) -> bool:
    return bool(await page.evaluate(f"() => Boolean({expr})"))


async def page_title(page) -> str:
    try:
        return (await page.title() or "").strip()
    except Exception:
        return ""


def save_html(probe: SiteProbe, round_num: int, step: int, label: str, html: str) -> Path:
    directory = out_dir(probe) / "rounds"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"r{round_num:03d}_{step:02d}_{label}.html"
    path.write_text(html, encoding="utf-8")
    return path


def default_action_labels(actions: list[dict[str, str]]) -> list[str]:
    labels: list[str] = []
    for action in actions:
        t = action["type"]
        if t == "url":
            data = action["data"]
            if "api/" in data or "entrypoint-api" in data:
                labels.append("api")
            elif "search" in data or "catalog" in data:
                labels.append("search_page")
            else:
                labels.append("navigate")
        elif t == "script":
            labels.append("script")
        elif t == "waitElement":
            labels.append("wait_element")
        else:
            labels.append(t)
    return labels


async def run_probe_action(page, action: dict[str, str]) -> None:
    action_type = action["type"]
    data = action["data"]
    wait_for = action.get("wait_for", f"pre#{RESULT_PRE_ID}")

    if action_type == "url":
        await page.goto(data, wait_until="domcontentloaded", timeout=60_000)
    elif action_type == "wait":
        await page.wait_for_timeout(int(data))
    elif action_type == "waitElement":
        await page.evaluate(f"async () => {{ {data} }}")
        if wait_for:
            await page.wait_for_selector(wait_for, timeout=90_000)
    elif action_type == "script":
        if action.get("expects_navigation", "true") == "true":
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=60_000):
                await page.evaluate(f"() => {{ {data} }}")
        else:
            await page.evaluate(f"() => {{ {data} }}")
        await page.wait_for_load_state("domcontentloaded", timeout=60_000)
    else:
        raise ValueError(f"Unknown action type: {action_type}")


async def inspect_step(
    probe: SiteProbe,
    page,
    *,
    label: str,
    t0: float,
    round_num: int,
    step: int,
    count_products: bool = True,
) -> StepResult:
    html = await page_content(page)
    path = save_html(probe, round_num, step, label, html)
    is_captcha = await captcha(page, probe.check_captcha)
    products = len(probe.parse_html(html)) if count_products else 0
    specs = 0
    if probe.parse_detail_html and "detail" in label:
        specs = len(probe.parse_detail_html(html))
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
        title=await page_title(page),
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


async def run_search_flow(
    probe: SiteProbe,
    page,
    query: str,
    *,
    round_num: int,
    t0: float,
) -> tuple[list[StepResult], bool, int]:
    actions = probe.build_actions(query)
    label_fn = probe.action_labels or default_action_labels
    labels = label_fn(actions)
    steps: list[StepResult] = []

    for idx, (action, label) in enumerate(zip(actions, labels, strict=False), start=1):
        await run_probe_action(page, action)
        count_products = label in ("api", "wait_element", "api_search") or action["type"] == "waitElement"
        step = await inspect_step(
            probe,
            page,
            label=label,
            t0=t0,
            round_num=round_num,
            step=idx,
            count_products=count_products,
        )
        steps.append(step)
        if step.blocked:
            return steps, True, 0
        if step.products:
            return steps, False, step.products

    final = steps[-1] if steps else None
    products = final.products if final else 0
    return steps, False, products


async def run_round(
    probe: SiteProbe,
    page,
    query: str,
    round_num: int,
    *,
    with_details: bool,
) -> tuple[bool, int]:
    t0 = time.perf_counter()
    steps, blocked, products = await run_search_flow(probe, page, query, round_num=round_num, t0=t0)

    for step in steps:
        print_step(step)

    if not blocked and with_details and probe.run_detail_flow and products:
        html = await page_content(page)
        parsed = probe.parse_html(html)
        link = next((p.product_link for p in parsed if p.product_link), None)
        if link:
            detail_steps, detail_blocked = await probe.run_detail_flow(probe, page, link, round_num=round_num, t0=t0)
            for step in detail_steps:
                print_step(step)
            blocked = detail_blocked

    log(
        f"Round {round_num} done in {time.perf_counter() - t0:.1f}s | "
        f"{'BLOCKED' if blocked else 'ok'} | products={products}"
    )
    return blocked, products


async def amain(probe: SiteProbe, *, description: str) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--query", default=probe.default_query)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()

    log(f"Site={probe.site} engine=cloakbrowser headless={headless(probe)} query={args.query!r}")
    log(f"Rounds={args.rounds} interval={args.interval}s details={args.details}")
    out_dir(probe).mkdir(parents=True, exist_ok=True)

    session_t0 = time.perf_counter()
    first_block_round: int | None = None
    first_success_round: int | None = None

    context = await launch_persistent_context_async(
        user_data_dir=session_dir(probe),
        headless=headless(probe),
        proxy=HTTP_PROXY,
        locale="ru-RU",
    )

    try:
        for round_num in range(1, args.rounds + 1):
            log(f"--- Round {round_num}/{args.rounds} ---")
            page = await context.new_page()
            blocked = False
            products = 0
            try:
                blocked, products = await run_round(
                    probe,
                    page,
                    args.query,
                    round_num,
                    with_details=args.details,
                )
                if blocked and first_block_round is None:
                    first_block_round = round_num
                    log(f"*** Block/captcha on round {round_num} ({time.perf_counter() - session_t0:.1f}s session) ***")
                    if not headless(probe):
                        log("Solve captcha in browser, or Ctrl+C.")
                        while await captcha(page, probe.check_captcha):
                            await asyncio.sleep(2)
                        log("Captcha cleared — continuing.")
                        first_block_round = None
            finally:
                await page.close()

            if blocked and first_block_round is not None:
                break

            if products and first_success_round is None:
                first_success_round = round_num

            if round_num < args.rounds and args.interval > 0:
                await asyncio.sleep(args.interval)
    finally:
        await context.close()

    summary = {
        "site": probe.site,
        "engine": "cloakbrowser",
        "query": args.query,
        "rounds_requested": args.rounds,
        "first_block_round": first_block_round,
        "first_success_round": first_success_round,
        "session_seconds": round(time.perf_counter() - session_t0, 2),
        "headless": headless(probe),
        "out_dir": str(out_dir(probe)),
    }
    path = out_dir(probe) / "summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Summary: {path}")

    if first_success_round:
        log(f"Got products on round {first_success_round}.")
        return 0
    if first_block_round:
        log(f"Blocked on round {first_block_round}.")
        return 1
    log("No block flag, but zero products.")
    return 1


def main(probe: SiteProbe, *, description: str) -> int:
    return asyncio.run(amain(probe, description=description))
