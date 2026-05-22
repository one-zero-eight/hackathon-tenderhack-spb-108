import asyncio

from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.api import docs
from src.logging_ import logger
from src.modules.search.ozon import run_ozon_parser
from src.modules.search.schemas import SearchParams, SearchResults
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
    logger.info("Running Yandex Market parser")
    yandex_market_task = asyncio.to_thread(run_yandex_market_parser, search_params.query)

    logger.info("Running Wildberries parser")
    wildberries_task = asyncio.to_thread(run_wildberries_parser, search_params.query)

    logger.info("Running Ozon parser")
    ozon_task = asyncio.to_thread(run_ozon_parser, search_params.query)

    results = await asyncio.gather(yandex_market_task, wildberries_task, ozon_task)

    return SearchResults(
        original_params=search_params,
        sources=results,
    )
