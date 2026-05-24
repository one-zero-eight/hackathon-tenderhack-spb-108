import asyncio

from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.api import docs
from src.logging_ import logger
from src.modules.search.common import get_browser_context
from src.modules.search.ozon import run_ozon_parser
from src.modules.search.parse_from_url import parse_url
from src.modules.search.region_geo import get_city_geo
from src.modules.search.rerank import rerank_search_source
from src.modules.search.schemas import (
    SearchParams,
    SearchResults,
    SearchSource,
    SourceType,
    SpellcheckRequest,
    SpellcheckResponse,
    TypofixSuggestion,
)
from src.modules.search.spellcheck import fetch_spellcheck_suggestions
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


async def _fetch_and_rerank(coro, query: str):
    source, suggestion = await coro
    if isinstance(source, list):
        reranked_sources = [await rerank_search_source(item, query) for item in source]
        return reranked_sources, suggestion
    return await rerank_search_source(source, query), suggestion


@router.post("/spellcheck", responses={200: {"description": "Spellcheck suggestions"}})
async def spellcheck(spellcheck_request: SpellcheckRequest) -> SpellcheckResponse:
    """
    Return spellcheck suggestions for a single word.
    """
    logger.info("Running spellcheck for %r (%s)", spellcheck_request.word, spellcheck_request.language)
    suggestions = await fetch_spellcheck_suggestions(
        spellcheck_request.word,
        spellcheck_request.language,
    )
    return SpellcheckResponse(
        word=spellcheck_request.word,
        language=spellcheck_request.language,
        suggestions=suggestions,
    )


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
    original_query = search_params.query
    search_query = original_query

    run_ozon = not search_params.source_types or SourceType.ozon in search_params.source_types
    run_wildberries = not search_params.source_types or SourceType.wildberries in search_params.source_types
    run_yandex_market = not search_params.source_types or SourceType.yandex_market in search_params.source_types
    run_runet = not search_params.source_types or SourceType.runet in search_params.source_types

    sources: list[SearchSource] = []
    typofix_suggestions: list[TypofixSuggestion] = []

    if run_ozon and search_params.spellcheck:
        logger.info("Running Ozon parser first for %r to resolve spellcheck", original_query)
        async with request_timing.stage("fetch_sources.ozon"):
            try:
                ozon_source, ozon_typofix = await _fetch_and_rerank(
                    run_ozon_parser(
                        None,
                        original_query,
                        region=search_params.region,
                        spellcheck=True,
                    ),
                    original_query,
                )
            except Exception:
                logger.error("Ozon search source failed", exc_info=True)
            else:
                if isinstance(ozon_source, list):
                    sources.extend(ozon_source)
                else:
                    sources.append(ozon_source)
                if (
                    ozon_typofix
                    and queries_differ(original_query, ozon_typofix)
                    and is_plausible_typofix(original_query, ozon_typofix)
                ):
                    typofix_suggestions.append(TypofixSuggestion(source=SourceType.ozon, suggestion=ozon_typofix))
                    search_query = ozon_typofix
                    logger.info("Using Ozon-corrected query %r for remaining sources", search_query)
        run_ozon = False

    tasks: list = []
    if run_ozon:
        logger.info("Running Ozon parser for %r (spellcheck=%s)", search_query, search_params.spellcheck)
        tasks.append(
            _fetch_and_rerank(
                run_ozon_parser(
                    None,
                    search_query,
                    region=search_params.region,
                    spellcheck=search_params.spellcheck,
                ),
                search_query,
            )
        )
    if run_wildberries:
        logger.info("Running Wildberries parser for %r (spellcheck=%s)", search_query, search_params.spellcheck)
        tasks.append(
            _fetch_and_rerank(
                run_wildberries_parser(
                    None,
                    search_query,
                    region=search_params.region,
                    spellcheck=search_params.spellcheck,
                ),
                search_query,
            )
        )
    if run_yandex_market:
        logger.info("Running Yandex Market parser for %r (spellcheck=%s)", search_query, search_params.spellcheck)
        tasks.append(
            _fetch_and_rerank(
                run_yandex_market_parser(
                    None,
                    search_query,
                    region=search_params.region,
                    spellcheck=search_params.spellcheck,
                ),
                search_query,
            )
        )
    if run_runet:
        logger.info("Running Runet (Whoogle) parser for %r", search_query)
        tasks.append(_fetch_and_rerank(run_runet_parser(search_query, region=search_params.region), search_query))

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
            if not search_params.spellcheck:
                continue
            if not suggestion or not queries_differ(original_query, suggestion):
                continue
            typofix_source = source[0].source_type if isinstance(source, list) else source.source_type
            if not is_plausible_typofix(original_query, suggestion):
                continue
            if any(item.source == typofix_source and item.suggestion == suggestion for item in typofix_suggestions):
                continue
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
