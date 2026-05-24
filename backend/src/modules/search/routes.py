from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.api import docs
from src.logging_ import logger
from src.modules.search.jobs import JobInfo, get_all_jobs, get_job, start_job_search
from src.modules.search.jobs import cancel_job as cancel_search_job
from src.modules.search.parse_from_url import parse_url
from src.modules.search.schemas import (
    SearchParams,
    SearchResults,
    SpellcheckRequest,
    SpellcheckResponse,
)
from src.modules.search.spellcheck import fetch_spellcheck_suggestions
from src.modules.search.whoogle import run_search

router = APIRouter(
    prefix="/search",
    tags=["Search"],
    route_class=AutoDeriveResponsesAPIRoute,
)
_description = """
Search for products.
"""
docs.TAGS_INFO.append({"description": _description, "name": str(router.tags[0])})


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


@router.post("/test-search", responses={200: {"description": "Found products"}})
async def test_search(query: str) -> SearchResults:
    """
    Search via Whoogle, then parse products from the top result pages in parallel.
    """
    logger.info("Running test search for %r", query)
    return await run_search(query)


@router.post("/test-parse-from-url", responses={200: {"description": "Found products"}})
async def parse_from_url_endpoint(url: str) -> SearchResults:
    """
    Fetch a page by URL, extract catalog markdown, and parse products.
    """
    logger.info("Parsing products from URL: %s", url)
    return await parse_url(url)


@router.post("/jobs/start", responses={200: {"description": "Started job"}})
async def start_job(search_params: SearchParams) -> JobInfo:
    return await start_job_search(search_params)


@router.get("/jobs/{job_id}", responses={200: {"description": "Job information"}})
async def get_job_endpoint(job_id: int) -> JobInfo:
    return await get_job(job_id)


@router.post("/jobs/{job_id}/cancel", responses={200: {"description": "Canceled job"}})
async def cancel_job_endpoint(job_id: int) -> JobInfo:
    return await cancel_search_job(job_id)


@router.get("/jobs/", responses={200: {"description": "All jobs information"}})
async def get_all_jobs_endpoint() -> list[JobInfo]:
    return await get_all_jobs()
