"""Fetch product characteristics from detail pages (limited per source)."""

import re
from collections.abc import Callable

from src.logging_ import logger
from src.modules.search.common import (
    append_characteristic,
    check_captcha,
    wait_captcha_solved,
)
from src.modules.search.schemas import SearchResult

DETAIL_CHARACTERISTICS_LIMIT = 3

_SPECS_TABLE_ROW_RE = re.compile(
    r'<th class="cellKey[^"]*"[^>]*>.*?cellWrapper[^"]*"[^>]*>([^<]+)</span>.*?</th>\s*'
    r'<td class="cellValue[^"]*"[^>]*>(.*?)</td>',
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


async def enrich_product_characteristics(
    page,
    products: list[SearchResult],
    *,
    fetch_characteristics: Callable,
    check_captcha_expr: str,
    site_name: str,
    limit: int = DETAIL_CHARACTERISTICS_LIMIT,
) -> None:
    attempted = 0
    for product in products:
        if attempted >= limit:
            break
        if not product.product_link:
            continue
        attempted += 1
        logger.info(
            "Loading detail page for %s (%d/%d): %s",
            site_name,
            attempted,
            limit,
            product.name[:60],
        )
        try:
            specs = await fetch_characteristics(page, product.product_link)
        except Exception as exc:
            logger.warning("Detail characteristics failed for %s: %s", product.product_link, exc)
            continue
        if await check_captcha(page, check_captcha_expr, site_name):
            await wait_captcha_solved(page, check_captcha_expr)
            try:
                specs = await fetch_characteristics(page, product.product_link)
            except Exception as exc:
                logger.warning("Detail retry failed for %s: %s", product.product_link, exc)
                continue
        if specs:
            product.characteristics = specs
            logger.info("Got %d characteristics for %s", len(specs), product.name[:60])
