"""Whoogle search adapter (JSON API)."""

import asyncio
import os
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.config import settings
from src.logging_ import logger
from src.modules.search.parse_from_url import parse_url
from src.modules.search.schemas import SearchParams, SearchResults
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

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search_title_map(
        self,
        query: str,
        limit: int,
        search_type: str = "",
        near: str = "",
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
                near=near,
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
        near: str = "",
    ) -> WhoogleSearchResponse:
        params = {"q": query, "format": "json"}
        if start > 0:
            params["start"] = str(start)
        if search_type:
            params["tbm"] = search_type
        if near:
            params["near"] = near

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


async def run_search(query: str, *, limit: int = 5) -> SearchResults:
    request_timing = TimingRecorder.start()

    async with request_timing.stage("whoogle_search"):
        urls = await asyncio.to_thread(search_top_urls, query, limit)
    logger.info("Whoogle returned %d URLs for query %r", len(urls), query)

    if not urls:
        return SearchResults(
            original_params=SearchParams(query=query),
            sources=[],
            timing=request_timing.to_request_timing(),
        )

    async with request_timing.stage("parse_sources"):
        parse_results = await asyncio.gather(*(parse_url(url) for url in urls))

    sources = [source for result in parse_results for source in result.sources]
    logger.info("Parsed %d sources (%d products total)", len(sources), sum(len(s.results) for s in sources))

    return SearchResults(
        original_params=SearchParams(query=query),
        sources=sources,
        timing=request_timing.to_request_timing(),
    )
