import asyncio

from cloakbrowser import launch_persistent_context_async
from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.api import docs
from src.logging_ import logger
from src.modules.search.common import HTTP_PROXY, site_paths
from src.modules.search.ozon import run_ozon_parser
from src.modules.search.schemas import SearchParams, SearchResults, SourceType
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

    session_dir, _ = site_paths("shared")
    session_dir.mkdir(parents=True, exist_ok=True)
    # headless = headless_from_env("HEADLESS")

    if HTTP_PROXY:
        logger.info("Using HTTP proxy: %s", HTTP_PROXY.split("@")[-1])

    context = await launch_persistent_context_async(
        user_data_dir=session_dir,
        headless=False,
        proxy=HTTP_PROXY,
        locale="ru-RU",
    )

    try:
        run_yandex_market = not search_params.source_types or SourceType.yandex_market in search_params.source_types
        if run_yandex_market:
            logger.info("Running Yandex Market parser")
            yandex_market_task = run_yandex_market_parser(context, search_params.query)
        else:
            yandex_market_task = asyncio.sleep(0)

        run_wildberries = not search_params.source_types or SourceType.wildberries in search_params.source_types
        if run_wildberries:
            logger.info("Running Wildberries parser")
            wildberries_task = run_wildberries_parser(context, search_params.query)
        else:
            wildberries_task = asyncio.sleep(0)

        run_ozon = not search_params.source_types or SourceType.ozon in search_params.source_types
        if run_ozon:
            logger.info("Running Ozon parser")
            ozon_task = run_ozon_parser(context, search_params.query)
        else:
            ozon_task = asyncio.sleep(0)

        results = await asyncio.gather(yandex_market_task, wildberries_task, ozon_task)
    finally:
        await context.close()

    return SearchResults(
        original_params=search_params,
        sources=[source for source in results if source is not None],
    )
