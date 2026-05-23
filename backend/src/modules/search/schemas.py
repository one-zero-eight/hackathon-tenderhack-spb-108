from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    yandex_market = "yandex_market"
    wildberries = "wildberries"
    ozon = "ozon"
    runet = "runet"


class SearchParams(BaseModel):
    query: str
    "User search input"
    region: str | None = None
    "Region name. None means all regions"
    source_types: list[SourceType] | None = None
    "Source types to search in. None means all sources, [] means all sources"


class SearchResult(BaseModel):
    name: str
    characteristics: dict[str, str] = Field(default_factory=dict)
    product_link: str | None = None
    price: str | None = None
    image_link: str | None = None
    rating: str | None = None
    reviews: str | None = None


class SearchSource(BaseModel):
    source_type: SourceType
    source_url: str
    source_title: str
    source_favicon_url: str | None
    results: list[SearchResult]


class SearchResults(BaseModel):
    original_params: SearchParams
    sources: list[SearchSource]
