from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


class SourceType(StrEnum):
    yandex_market = "yandex_market"
    wildberries = "wildberries"
    ozon = "ozon"
    runet = "runet"


class SpellcheckLanguage(StrEnum):
    ru_RU = "ru-RU"
    en_US = "en-US"


class SearchParams(BaseModel):
    query: str
    "User search input"
    region: str | None = None
    "Regional capital city name (from regions.ts). None — no geo override"
    source_types: list[SourceType] | None = None
    "Source types to search in. None means all sources, [] means all sources"
    short: bool = False
    "Short search. Used for dev purposes, it will return only 4 results from each source."
    spellcheck: bool = True
    "When false, marketplaces search the exact query without auto-correction."


class StageTiming(BaseModel):
    name: str
    duration_ms: float
    started_at: str
    ended_at: str


class ProductTiming(BaseModel):
    duration_ms: float
    started_at: str
    ended_at: str
    stages: list[StageTiming] = Field(default_factory=list)


class SourceTiming(BaseModel):
    duration_ms: float
    started_at: str
    ended_at: str
    stages: list[StageTiming] = Field(default_factory=list)


class RequestTiming(BaseModel):
    duration_ms: float
    started_at: str
    ended_at: str
    stages: list[StageTiming] = Field(default_factory=list)


class SearchResult(BaseModel):
    name: str
    characteristics: dict[str, str] = Field(default_factory=dict)
    product_link: str | None = None
    price: str | None = None
    image_link: str | None = None
    image_links: list[str] = Field(default_factory=list)
    rating: str | None = None
    reviews: str | None = None
    rerank_score: float | None = None
    relevant: bool = True
    timing: ProductTiming | None = None


class SearchSource(BaseModel):
    source_type: SourceType
    source_url: str
    source_title: str
    source_favicon_url: str | None

    @computed_field
    @property
    def results_count(self) -> int:
        """Number of products found for this source."""
        return len(self.results)

    results: list[SearchResult]
    timing: SourceTiming | None = None


class TypofixSuggestion(BaseModel):
    source: SourceType
    suggestion: str


class SearchResults(BaseModel):
    original_params: SearchParams
    typofix_suggestions: list[TypofixSuggestion] = Field(default_factory=list)
    sources: list[SearchSource]
    timing: RequestTiming | None = None


class SpellcheckRequest(BaseModel):
    word: str = Field(min_length=3)
    "Single word from the search query to check."
    language: SpellcheckLanguage
    "LanguageTool locale used for spellcheck."


class SpellcheckResponse(BaseModel):
    word: str
    language: SpellcheckLanguage
    suggestions: list[str] = Field(default_factory=list)
