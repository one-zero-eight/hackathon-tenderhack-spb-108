from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.api import docs

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
async def search():
    """
    Search for products.
    """
    return []
