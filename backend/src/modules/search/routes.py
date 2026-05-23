import asyncio

from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.api import docs
from src.logging_ import logger
from src.modules.search.common import get_browser_context
from src.modules.search.ozon import run_ozon_parser
from src.modules.search.parse_from_url import parse_url
from src.modules.search.region_geo import get_city_geo
from src.modules.search.schemas import (
    SearchParams,
    SearchResults,
    SearchSource,
    SourceType,
    TypofixSuggestion,
)
from src.modules.search.timing import TimingRecorder
from src.modules.search.typofix import is_plausible_typofix, queries_differ
from src.modules.search.whoogle import run_runet_parser, run_search
from src.modules.search.wildberries import run_wildberries_parser
from src.modules.search.yandex_market import run_yandex_market_parser

router = APIRouter(
    prefix="/search",
    tags=["Search"],
    route_class=AutoDeriveResponsesAPIRoute,
)
_description = """
Search for products.
"""
docs.TAGS_INFO.append({"description": _description, "name": str(router.tags[0])})


@router.post("/search", responses={200: {"description": "Found products"}})
async def search(search_params: SearchParams) -> SearchResults:
    """
    Search for products.
    """
    logger.info(f"Running search for {search_params}")
    if search_params.region and get_city_geo(search_params.region) is None:
        logger.warning("Unknown region city %r — geo override skipped", search_params.region)

    request_timing = TimingRecorder.start()
    await get_browser_context()
    search_query = search_params.query

    run_ozon = not search_params.source_types or SourceType.ozon in search_params.source_types
    run_wildberries = not search_params.source_types or SourceType.wildberries in search_params.source_types
    run_yandex_market = not search_params.source_types or SourceType.yandex_market in search_params.source_types
    run_runet = not search_params.source_types or SourceType.runet in search_params.source_types

    sources: list[SearchSource] = []
    typofix_suggestions: list[TypofixSuggestion] = []

    tasks: list = []
    if run_ozon:
        logger.info("Running Ozon parser for %r", search_query)
        tasks.append(run_ozon_parser(None, search_query, region=search_params.region))
    if run_wildberries:
        logger.info("Running Wildberries parser for %r", search_query)
        tasks.append(run_wildberries_parser(None, search_query, region=search_params.region))
    if run_yandex_market:
        logger.info("Running Yandex Market parser for %r", search_query)
        tasks.append(run_yandex_market_parser(None, search_query, region=search_params.region))
    if run_runet:
        logger.info("Running Runet (Whoogle) parser for %r", search_query)
        tasks.append(run_runet_parser(search_query))

    if tasks:
        async with request_timing.stage("fetch_sources"):
            gathered = await asyncio.gather(*tasks, return_exceptions=True)

        for item in gathered:
            if isinstance(item, BaseException):
                logger.error("Search source failed", exc_info=item)
                continue
            source, suggestion = item
            if isinstance(source, list):
                sources.extend(source)
            else:
                sources.append(source)
            if suggestion and queries_differ(search_params.query, suggestion):
                typofix_source = source[0].source_type if isinstance(source, list) else source.source_type
                if is_plausible_typofix(search_params.query, suggestion) and not any(
                    t.source == typofix_source and t.suggestion == suggestion for t in typofix_suggestions
                ):
                    typofix_suggestions.append(TypofixSuggestion(source=typofix_source, suggestion=suggestion))

    if search_params.short:
        for source in sources:
            source.results = source.results[:4]
    return SearchResults(
        original_params=search_params,
        sources=sources,
        typofix_suggestions=typofix_suggestions,
        timing=request_timing.to_request_timing(),
    )


@router.post("/test-search", responses={200: {"description": "Found products"}})
async def test_search(query: str) -> SearchResults:
    """
    Search via Whoogle, then parse products from the top result pages in parallel.
    """
    logger.info("Running test search for %r", query)
    return await run_search(query)


@router.post("/test-parse-from-url", responses={200: {"description": "Found products"}})
async def parse_from_url(url: str) -> SearchResults:
    """
    Fetch a page by URL, extract catalog markdown, and parse products.
    """
    logger.info("Parsing products from URL: %s", url)
    return await parse_url(url)
