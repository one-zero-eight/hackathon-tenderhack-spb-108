"""Fetch a catalog page by URL, convert to markdown, and extract products."""

import asyncio

from pydefuddle import defuddle

from src.logging_ import logger
from src.modules.search.common import get_browser_context, page_content
from src.modules.search.extract_product_infos import extract_product_infos
from src.modules.search.schemas import SearchParams, SearchResult, SearchResults, SearchSource, SourceType
from src.modules.search.timing import TimingRecorder


async def fetch_page_html(url: str) -> str:
    context = await get_browser_context()
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        return await page_content(page)
    finally:
        await page.close()


def html_to_markdown(html: str, url: str) -> tuple[str, str, str | None]:
    result = defuddle(html, url=url)
    title = (result.title or result.site_title or url).strip()
    return result.markdown or "", title, result.favicon or None


async def parse_url(url: str) -> SearchResults:
    request_timing = TimingRecorder.start()

    async with request_timing.stage("fetch_page"):
        html = await fetch_page_html(url)
    logger.info("Fetched %d bytes of HTML from %s", len(html), url)

    async with request_timing.stage("defuddle"):
        markdown, source_title, favicon = await asyncio.to_thread(html_to_markdown, html, url)
    logger.info("Defuddle produced %d chars of markdown", len(markdown))

    if len(markdown):
        async with request_timing.stage("extract_products"):
            products: list[SearchResult] = await asyncio.to_thread(extract_product_infos, markdown, url)
        logger.info("Extracted %d products from %s", len(products), url)
    else:
        products = []

    return SearchResults(
        original_params=SearchParams(query=url),
        sources=[
            SearchSource(
                source_type=SourceType.runet,
                source_url=url,
                source_title=source_title,
                source_favicon_url=favicon,
                results=products,
            )
        ],
        timing=request_timing.to_request_timing(),
    )
