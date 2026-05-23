"""Fetch product characteristics from detail pages (limited per source)."""

from collections.abc import Callable

from src.logging_ import logger
from src.modules.search.common import (
    append_characteristic,
    check_captcha,
    wait_captcha_solved,
)
from src.modules.search.schemas import SearchResult

DETAIL_CHARACTERISTICS_LIMIT = 3


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


def enrich_product_characteristics(
    page,
    products: list[SearchResult],
    *,
    fetch_characteristics: Callable[[object, str], dict[str, str]],
    check_captcha_expr: str,
    site_name: str,
    limit: int = DETAIL_CHARACTERISTICS_LIMIT,
) -> None:
    enriched = 0
    for product in products:
        if enriched >= limit:
            break
        if not product.product_link:
            continue
        logger.info(
            "Loading detail page for %s (%d/%d): %s",
            site_name,
            enriched + 1,
            limit,
            product.name[:60],
        )
        try:
            specs = fetch_characteristics(page, product.product_link)
        except Exception as exc:
            logger.warning("Detail characteristics failed for %s: %s", product.product_link, exc)
            continue
        if check_captcha(page, check_captcha_expr, site_name):
            wait_captcha_solved(page, check_captcha_expr)
            try:
                specs = fetch_characteristics(page, product.product_link)
            except Exception as exc:
                logger.warning("Detail retry failed for %s: %s", product.product_link, exc)
                continue
        if specs:
            product.characteristics = specs
            enriched += 1
            logger.info("Got %d characteristics for %s", len(specs), product.name[:60])
