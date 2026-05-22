from typing import Literal

from pydantic import BaseModel, Field


class SearchParams(BaseModel):
    query: str
    "User search input"
    region: str | None
    "Region name. None means all regions"


class SearchResult(BaseModel):
    name: str
    characteristics: dict[str, str] = Field(default_factory=dict)
    price: str | None
    image_link: str | None


class SearchSource(BaseModel):
    source_type: Literal["yandex_market", "wildberries", "ozon", "runet"]
    source_url: str
    source_title: str
    source_favicon_url: str | None
    results: list[SearchResult]


class SearchResults(BaseModel):
    original_params: SearchParams
    sources: list[SearchSource]
