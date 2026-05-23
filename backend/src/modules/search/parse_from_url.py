"""Fetch a catalog page by URL, convert to markdown, and extract products."""

import asyncio
import re
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

from src.logging_ import logger
from src.modules.search.common import open_browser_page, page_content, scripts_dir, site_paths
from src.modules.search.extract_product_infos import extract_product_infos
from src.modules.search.markdown_urls import compress_markdown_urls, save_url_map
from src.modules.search.schemas import SearchParams, SearchResult, SearchResults, SearchSource, SourceType
from src.modules.search.timing import TimingRecorder
from src.modules.search.turndown_markdown import page_to_markdown


async def fetch_page_content(url: str) -> tuple[str, str, str, str | None]:
    page = await open_browser_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        # await page.wait_for_timeout(5000)
        html = await page_content(page)
        markdown, title, favicon = await page_to_markdown(page, url)
        return html, markdown, title, favicon
    finally:
        # await page.close()
        pass


def _url_file_stem(url: str) -> str:
    parsed = urlparse(url)
    host = re.sub(r"[^\w.-]", "_", parsed.netloc or "unknown")
    return f"{host}_{sha256(url.encode()).hexdigest()[:10]}"


def _save_parse_artifacts(
    url: str,
    html: str,
    markdown: str,
    *,
    compressed_markdown: str | None = None,
    url_map: dict[str, str] | None = None,
) -> None:
    _, html_dir = site_paths("runet")
    md_dir: Path = scripts_dir() / "out" / "runet" / "md"
    stem = _url_file_stem(url)
    html_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)
    html_path = html_dir / f"{stem}.html"
    md_path = md_dir / f"{stem}.md"
    html_path.write_text(html, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    logger.info("Saved HTML to %s", html_path)
    logger.info("Saved markdown to %s", md_path)
    if compressed_markdown is not None:
        compressed_path = md_dir / f"{stem}.compressed.md"
        compressed_path.write_text(compressed_markdown, encoding="utf-8")
        logger.info("Saved compressed markdown to %s", compressed_path)
    if url_map:
        map_path = md_dir / f"{stem}.urls.json"
        save_url_map(map_path, url_map)
        logger.info("Saved URL map (%d entries) to %s", len(url_map), map_path)


async def parse_url(url: str) -> SearchResults:
    request_timing = TimingRecorder.start()

    async with request_timing.stage("fetch_page"):
        html, markdown, source_title, favicon = await fetch_page_content(url)
    logger.info("%s Fetched %d bytes of HTML", url, len(html))
    logger.info("%s Turndown produced %d chars of markdown", url, len(markdown))

    url_map: dict[str, str] = {}
    markdown_for_llm = markdown
    if markdown:
        markdown_for_llm, url_map = compress_markdown_urls(markdown)
        logger.info(
            "%s Compressed markdown for LLM: %d -> %d chars (%d URLs)",
            url,
            len(markdown),
            len(markdown_for_llm),
            len(url_map),
        )
    _save_parse_artifacts(
        url,
        html,
        markdown,
        compressed_markdown=markdown_for_llm if url_map else None,
        url_map=url_map or None,
    )

    if markdown_for_llm:
        async with request_timing.stage("extract_products"):
            products: list[SearchResult] = await asyncio.to_thread(
                extract_product_infos,
                markdown_for_llm,
                url,
                url_map,
            )
        logger.info("%s Extracted %d products", url, len(products))
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
