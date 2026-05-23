"""Fetch product characteristics from detail pages (limited per source)."""

import asyncio
import re
from collections.abc import Awaitable, Callable

from src.logging_ import logger
from src.modules.search.common import (
    append_characteristic,
    check_captcha,
    is_browser_closed_error,
    open_browser_page,
    release_browser_page,
    wait_captcha_solved,
)
from src.modules.search.schemas import SearchResult
from src.modules.search.timing import TimingRecorder

DETAIL_CHARACTERISTICS_LIMIT = 3

_SPECS_TABLE_ROW_RE = re.compile(
    r'<th class="cellKey[^"]*"[^>]*>.*?cellWrapper[^"]*"[^>]*>([^<]+)</span\s*>.*?</th>\s*'
    r'<td class="cellValue[^"]*"[^>]*>(.*?)</td\s*>',
    re.DOTALL,
)


def _strip_html_text(raw: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()


def parse_specs_table_html(html: str) -> dict[str, str]:
    specs: dict[str, str] = {}
    for match in _SPECS_TABLE_ROW_RE.finditer(html):
        append_characteristic(specs, match.group(1), _strip_html_text(match.group(2)))
    return specs


def specs_from_raw(rows: object) -> dict[str, str]:
    specs: dict[str, str] = {}
    if not isinstance(rows, list):
        return specs
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            append_characteristic(specs, str(row[0]), row[1])
        elif isinstance(row, str) and ":" in row:
            name, _, value = row.partition(":")
            append_characteristic(specs, name, value)
    return specs


async def _enrich_one_product(
    product: SearchResult,
    *,
    fetch_characteristics: Callable[[object, str], Awaitable[dict[str, str]]],
    check_captcha_expr: str,
    site_name: str,
    index: int,
    total: int,
) -> None:
    recorder = TimingRecorder.start()
    logger.info(
        "Loading detail page for %s (%d/%d): %s | %s",
        site_name,
        index,
        total,
        product.name[:60],
        product.product_link,
    )
    detail_page = await open_browser_page()
    try:
        try:
            async with recorder.stage("fetch"):
                specs = await fetch_characteristics(detail_page, product.product_link)
        except Exception as exc:
            logger.warning("Detail characteristics failed for %s: %s", product.product_link, exc)
            product.timing = recorder.to_product_timing()
            return
        if detail_page.is_closed():
            product.timing = recorder.to_product_timing()
            return
        try:
            captcha = await check_captcha(detail_page, check_captcha_expr, site_name)
        except Exception as exc:
            if is_browser_closed_error(exc):
                logger.warning("Detail page closed before captcha check for %s", product.product_link)
                product.timing = recorder.to_product_timing()
                return
            raise
        if captcha:
            await wait_captcha_solved(detail_page, check_captcha_expr)
            try:
                async with recorder.stage("fetch_retry"):
                    specs = await fetch_characteristics(detail_page, product.product_link)
            except Exception as exc:
                logger.warning("Detail retry failed for %s: %s", product.product_link, exc)
                product.timing = recorder.to_product_timing()
                return
        if specs:
            product.characteristics = specs
            logger.info(
                "Got %d characteristics for %s | %s",
                len(specs),
                product.name[:60],
                product.product_link,
            )
    finally:
        await release_browser_page(detail_page)
        product.timing = recorder.to_product_timing()


async def enrich_product_characteristics(
    page,
    products: list[SearchResult],
    *,
    fetch_characteristics: Callable,
    check_captcha_expr: str,
    site_name: str,
    limit: int = DETAIL_CHARACTERISTICS_LIMIT,
) -> None:
    candidates = [p for p in products if p.product_link][:limit]
    if not candidates:
        return
    total = len(candidates)
    results = await asyncio.gather(
        *[
            _enrich_one_product(
                product,
                fetch_characteristics=fetch_characteristics,
                check_captcha_expr=check_captcha_expr,
                site_name=site_name,
                index=i,
                total=total,
            )
            for i, product in enumerate(candidates, start=1)
        ],
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("Detail enrich task failed for %s: %s", site_name, result)
