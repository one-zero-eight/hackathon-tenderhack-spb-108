"""Whoogle search adapter (JSON API)."""

import asyncio
import os
from typing import Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.config import settings
from src.logging_ import logger
from src.modules.search.parse_from_url import parse_url
from src.modules.search.schemas import SearchParams, SearchResults, SearchSource, SourceType
from src.modules.search.timing import TimingRecorder


class WhoogleAdapterError(Exception):
    """Base adapter error."""


class WhoogleSearchBlocked(WhoogleAdapterError):
    """Raised when the upstream search is temporarily blocked."""


class WhoogleSearchRedirect(WhoogleAdapterError):
    """Raised when the query resolves to a direct redirect."""

    def __init__(self, redirect_url: str) -> None:
        self.redirect_url = redirect_url
        super().__init__(redirect_url)


class RunetProgress(Protocol):
    async def on_discovered(self, sources: list[SearchSource]) -> None: ...

    async def on_parsed(self, source: SearchSource) -> None: ...


class WhoogleAdapterSettings(BaseModel):
    base_url: str = "http://127.0.0.1:5000"
    timeout_seconds: float = 10.0
    page_size: int = 10
    verify_ssl: bool = True

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return normalized

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page_size must be greater than 0")
        return value


class WhoogleSearchResult(BaseModel):
    href: str
    text: str = ""
    title: str = ""
    content: str = ""


class WhoogleSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = ""
    search_type: str = ""
    results: list[WhoogleSearchResult] = Field(default_factory=list)
    redirect: str | None = None
    blocked: bool = False
    error: bool = False
    error_message: str | None = None


class WhoogleSearchAdapter:
    def __init__(
        self,
        settings: WhoogleAdapterSettings,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=self.settings.base_url,
            timeout=self.settings.timeout_seconds,
            follow_redirects=False,
            verify=self.settings.verify_ssl,
            headers={"Accept": "application/json"},
        )

    def __enter__(self) -> "WhoogleSearchAdapter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search_title_map(
        self,
        query: str,
        limit: int,
        search_type: str = "",
    ) -> dict[str, str]:
        if limit < 1:
            return {}

        title_map: dict[str, str] = {}
        page_index = 0

        while len(title_map) < limit:
            start = page_index * self.settings.page_size
            page = self._fetch_page(
                query=query,
                start=start,
                search_type=search_type,
            )
            if not page.results:
                break

            previous_size = len(title_map)
            for result in page.results:
                title = (result.title or result.text or result.href).strip() or result.href
                unique_title = self._dedupe_title(title, result.href, title_map)
                if unique_title is None:
                    continue

                title_map[unique_title] = result.href
                if len(title_map) >= limit:
                    break

            if len(title_map) == previous_size or len(page.results) < self.settings.page_size:
                break

            page_index += 1

        return title_map

    def _fetch_page(
        self,
        query: str,
        start: int = 0,
        search_type: str = "",
    ) -> WhoogleSearchResponse:
        params = {"q": query, "format": "json"}
        if start > 0:
            params["start"] = str(start)
        if search_type:
            params["tbm"] = search_type

        response = self._client.get("/search", params=params)
        payload = response.json()
        parsed = WhoogleSearchResponse.model_validate(payload)

        if response.status_code in (302, 303):
            raise WhoogleSearchRedirect(parsed.redirect or "")
        if response.status_code == 503 and parsed.blocked:
            raise WhoogleSearchBlocked(parsed.error_message or "Search is temporarily blocked")
        if parsed.error:
            raise WhoogleAdapterError(parsed.error_message or "Whoogle returned an error")

        response.raise_for_status()
        return parsed

    @staticmethod
    def _dedupe_title(title: str, href: str, title_map: dict[str, str]) -> str | None:
        existing = title_map.get(title)
        if existing is None:
            return title
        if existing == href:
            return None

        suffix = 2
        while True:
            candidate = f"{title} ({suffix})"
            existing = title_map.get(candidate)
            if existing is None:
                return candidate
            if existing == href:
                return None
            suffix += 1


def default_settings() -> WhoogleAdapterSettings:
    return WhoogleAdapterSettings(
        base_url=settings.whoogle_base_url,
        timeout_seconds=float(os.getenv("WHOOGLE_TIMEOUT_SECONDS", "10")),
    )


def search_top_urls(query: str, limit: int = 5) -> list[str]:
    with WhoogleSearchAdapter(default_settings()) as adapter:
        title_map = adapter.search_title_map(query=query, limit=limit)
    return list(title_map.values())


def placeholder_from_url(url: str) -> SearchSource:
    host = urlparse(url).netloc or url
    return SearchSource(
        source_type=SourceType.runet,
        source_url=url,
        source_title=host,
        source_favicon_url=f"https://www.google.com/s2/favicons?domain={host}&sz=64",
        results=[],
        is_parsing=True,
    )


async def run_runet_parser(
    query: str,
    *,
    limit: int = 5,
    region: str | None = None,
    progress: RunetProgress | None = None,
) -> tuple[list[SearchSource], None]:
    recorder = TimingRecorder.start()

    whoogle_search_query = query
    if "купить" not in query:
        whoogle_search_query = "купить " + whoogle_search_query
    if region:
        whoogle_search_query = whoogle_search_query + " " + region

    async with recorder.stage("whoogle_search"):
        urls = await asyncio.to_thread(search_top_urls, whoogle_search_query, limit)
    logger.info("Whoogle returned %d URLs for query %r", len(urls), whoogle_search_query)

    if not urls:
        return [], None

    discovered = [placeholder_from_url(url) for url in urls]
    if progress is not None:
        await progress.on_discovered(discovered)

    async def parse_one(url: str) -> SearchSource:
        try:
            result = await parse_url(url)
            source = result.sources[0] if result.sources else placeholder_from_url(url)
        except Exception:
            logger.error("Failed to parse runet URL %s", url, exc_info=True)
            source = placeholder_from_url(url)
        source = source.model_copy(update={"is_parsing": False, "source_type": SourceType.runet})
        source_timing = recorder.to_source_timing()
        source.timing = source_timing
        if progress is not None:
            await progress.on_parsed(source)
        return source

    async with recorder.stage("parse_sources"):
        sources = await asyncio.gather(*(parse_one(url) for url in urls))

    logger.info(
        "Parsed %d runet sources (%d products total)",
        len(sources),
        sum(len(source.results) for source in sources),
    )
    return list(sources), None


async def run_search(query: str, *, limit: int = 5) -> SearchResults:
    request_timing = TimingRecorder.start()
    async with request_timing.stage("runet"):
        sources, _ = await run_runet_parser(query, limit=limit)
    return SearchResults(
        original_params=SearchParams(query=query),
        sources=sources,
        timing=request_timing.to_request_timing(),
    )
