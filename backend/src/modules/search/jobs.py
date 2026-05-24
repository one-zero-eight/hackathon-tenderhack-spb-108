import asyncio
from dataclasses import dataclass, field
from enum import StrEnum

from fastapi import HTTPException
from pydantic import BaseModel, Field

from src.logging_ import logger
from src.modules.search.common import get_browser_context
from src.modules.search.ozon import run_ozon_parser
from src.modules.search.region_geo import get_city_geo
from src.modules.search.rerank import rerank_search_source
from src.modules.search.schemas import (
    RequestTiming,
    SearchParams,
    SearchSource,
    SourceType,
    TypofixSuggestion,
)
from src.modules.search.timing import TimingRecorder
from src.modules.search.typofix import is_plausible_typofix, queries_differ
from src.modules.search.whoogle import RunetProgress, run_runet_parser
from src.modules.search.wildberries import run_wildberries_parser
from src.modules.search.yandex_market import run_yandex_market_parser


class JobStatus(StrEnum):
    PENDING = "PENDING"
    FINISHED = "FINISHED"


class SourceStatus(StrEnum):
    PENDING = "PENDING"
    FINISHED = "FINISHED"


class JobInfo(BaseModel):
    job_id: int
    job_status: JobStatus

    original_params: SearchParams
    typofix_suggestions: list[TypofixSuggestion] = Field(default_factory=list)
    sources: list[SearchSource]
    sources_statuses: list[SourceStatus]
    timing: RequestTiming | None = None


@dataclass
class _JobRecord:
    info: JobInfo
    planned_sources: list[SourceType]
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cancel_requested: bool = False
    task: asyncio.Task | None = None


class _JobRunetProgress(RunetProgress):
    def __init__(self, record: _JobRecord, query: str) -> None:
        self._record = record
        self._query = query

    async def on_discovered(self, sources: list[SearchSource]) -> None:
        await _append_sources(self._record, sources)

    async def on_parsed(self, source: SearchSource) -> None:
        try:
            reranked = await rerank_search_source(source, self._query)
        except Exception:
            logger.error("Runet rerank failed for %s", source.source_url, exc_info=True)
            reranked = source
        await _update_source_by_url(
            self._record,
            reranked.model_copy(update={"is_parsing": False, "source_type": SourceType.runet}),
        )


_jobs: dict[int, _JobRecord] = {}
_next_job_id = 1
_jobs_lock = asyncio.Lock()


def _sources_to_run(search_params: SearchParams) -> list[SourceType]:
    if search_params.source_types:
        return list(search_params.source_types)
    return list(SourceType)


def _source_index(planned_sources: list[SourceType], source_type: SourceType) -> int:
    return planned_sources.index(source_type)


async def _snapshot(record: _JobRecord) -> JobInfo:
    async with record.lock:
        return record.info.model_copy(deep=True)


async def _append_sources(record: _JobRecord, new_sources: list[SearchSource]) -> None:
    if not new_sources:
        return
    async with record.lock:
        if record.cancel_requested:
            return
        record.info.sources.extend(new_sources)


async def _update_source_by_url(record: _JobRecord, updated: SearchSource) -> None:
    async with record.lock:
        if record.cancel_requested:
            return
        for index, source in enumerate(record.info.sources):
            if source.source_url == updated.source_url:
                record.info.sources[index] = updated
                return
        record.info.sources.append(updated)


async def _replace_marketplace_source(
    record: _JobRecord,
    source_type: SourceType,
    updated: SearchSource,
) -> None:
    async with record.lock:
        if record.cancel_requested:
            return
        for index, source in enumerate(record.info.sources):
            if source.source_type == source_type:
                record.info.sources[index] = updated
                return
        record.info.sources.append(updated)


async def _mark_source_finished(record: _JobRecord, finished_types: list[SourceType]) -> None:
    async with record.lock:
        if record.cancel_requested:
            return
        for source_type in finished_types:
            index = _source_index(record.planned_sources, source_type)
            record.info.sources_statuses[index] = SourceStatus.FINISHED


async def _apply_typofix(record: _JobRecord, suggestions: list[TypofixSuggestion]) -> None:
    if not suggestions:
        return
    async with record.lock:
        if record.cancel_requested:
            return
        for item in suggestions:
            if any(
                existing.source == item.source and existing.suggestion == item.suggestion
                for existing in record.info.typofix_suggestions
            ):
                continue
            record.info.typofix_suggestions.append(item)


async def _finish_job(record: _JobRecord, timing: RequestTiming | None) -> None:
    async with record.lock:
        if timing is not None:
            record.info.timing = timing
        record.info.job_status = JobStatus.FINISHED


async def _publish_marketplace_source(
    record: _JobRecord,
    source_type: SourceType,
    raw_source: SearchSource,
    query: str,
) -> SearchSource:
    await _append_sources(record, [raw_source])
    try:
        reranked = await rerank_search_source(raw_source, query)
    except Exception:
        logger.error("%s rerank failed", source_type.value, exc_info=True)
        reranked = raw_source
    await _replace_marketplace_source(record, source_type, reranked)
    return reranked


async def _run_job_search(record: _JobRecord) -> None:
    search_params = record.info.original_params
    if search_params.region and get_city_geo(search_params.region) is None:
        logger.warning("Unknown region city %r — geo override skipped", search_params.region)

    request_timing = TimingRecorder.start()
    await get_browser_context()

    if record.cancel_requested:
        await _finish_job(record, request_timing.to_request_timing())
        return

    original_query = search_params.query
    search_query = original_query

    run_ozon = SourceType.ozon in record.planned_sources
    run_wildberries = SourceType.wildberries in record.planned_sources
    run_yandex_market = SourceType.yandex_market in record.planned_sources
    run_runet = SourceType.runet in record.planned_sources

    if run_ozon and search_params.spellcheck:
        logger.info("Running Ozon parser first for %r to resolve spellcheck", original_query)
        async with request_timing.stage("fetch_sources.ozon"):
            try:
                ozon_source, ozon_typofix = await run_ozon_parser(
                    None,
                    original_query,
                    region=search_params.region,
                    spellcheck=True,
                )
            except Exception:
                logger.error("Ozon search source failed", exc_info=True)
                await _mark_source_finished(record, [SourceType.ozon])
            else:
                if record.cancel_requested:
                    await _finish_job(record, request_timing.to_request_timing())
                    return
                await _publish_marketplace_source(record, SourceType.ozon, ozon_source, original_query)
                await _mark_source_finished(record, [SourceType.ozon])
                if (
                    ozon_typofix
                    and ozon_source.results
                    and queries_differ(original_query, ozon_typofix)
                    and is_plausible_typofix(original_query, ozon_typofix)
                ):
                    await _apply_typofix(
                        record,
                        [TypofixSuggestion(source=SourceType.ozon, suggestion=ozon_typofix)],
                    )
                    search_query = ozon_typofix
                    logger.info("Using Ozon-corrected query %r for remaining sources", search_query)
        run_ozon = False

    async def run_source(source_type: SourceType, coro):
        if record.cancel_requested:
            return
        try:
            raw_source, suggestion = await coro
        except Exception:
            logger.error("%s search source failed", source_type.value, exc_info=True)
            await _mark_source_finished(record, [source_type])
            return
        if record.cancel_requested:
            return

        published = await _publish_marketplace_source(record, source_type, raw_source, search_query)
        await _mark_source_finished(record, [source_type])

        if not search_params.spellcheck:
            return
        if not suggestion or not queries_differ(original_query, suggestion):
            return
        if not is_plausible_typofix(original_query, suggestion):
            return
        await _apply_typofix(
            record,
            [TypofixSuggestion(source=published.source_type, suggestion=suggestion)],
        )

    async def run_runet_source():
        if record.cancel_requested:
            return
        try:
            await run_runet_parser(
                search_query,
                region=search_params.region,
                progress=_JobRunetProgress(record, search_query),
            )
        except Exception:
            logger.error("Runet search source failed", exc_info=True)
        finally:
            await _mark_source_finished(record, [SourceType.runet])

    tasks: list[asyncio.Task] = []
    if run_ozon:
        logger.info("Running Ozon parser for %r (spellcheck=%s)", search_query, search_params.spellcheck)
        tasks.append(
            asyncio.create_task(
                run_source(
                    SourceType.ozon,
                    run_ozon_parser(
                        None,
                        search_query,
                        region=search_params.region,
                        spellcheck=search_params.spellcheck,
                    ),
                )
            )
        )
    if run_wildberries:
        logger.info(
            "Running Wildberries parser for %r (spellcheck=%s)",
            search_query,
            search_params.spellcheck,
        )
        tasks.append(
            asyncio.create_task(
                run_source(
                    SourceType.wildberries,
                    run_wildberries_parser(
                        None,
                        search_query,
                        region=search_params.region,
                        spellcheck=search_params.spellcheck,
                    ),
                )
            )
        )
    if run_yandex_market:
        logger.info(
            "Running Yandex Market parser for %r (spellcheck=%s)",
            search_query,
            search_params.spellcheck,
        )
        tasks.append(
            asyncio.create_task(
                run_source(
                    SourceType.yandex_market,
                    run_yandex_market_parser(
                        None,
                        search_query,
                        region=search_params.region,
                        spellcheck=search_params.spellcheck,
                    ),
                )
            )
        )
    if run_runet:
        logger.info("Running Runet (Whoogle) parser for %r", search_query)
        tasks.append(asyncio.create_task(run_runet_source()))

    if tasks:
        async with request_timing.stage("fetch_sources"):
            await asyncio.gather(*tasks, return_exceptions=True)

    if search_params.short:
        async with record.lock:
            for source in record.info.sources:
                source.results = source.results[:4]

    await _finish_job(record, request_timing.to_request_timing())


async def start_job_search(search_params: SearchParams) -> JobInfo:
    global _next_job_id  # noqa

    planned_sources = _sources_to_run(search_params)
    async with _jobs_lock:
        job_id = _next_job_id
        _next_job_id += 1
        record = _JobRecord(
            info=JobInfo(
                job_id=job_id,
                job_status=JobStatus.PENDING,
                original_params=search_params,
                sources=[],
                sources_statuses=[SourceStatus.PENDING] * len(planned_sources),
            ),
            planned_sources=planned_sources,
        )
        _jobs[job_id] = record

    logger.info("Started search job %s for %s", job_id, search_params)
    record.task = asyncio.create_task(_run_job_search(record))
    return await _snapshot(record)


def _get_record(job_id: int) -> _JobRecord:
    record = _jobs.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return record


async def get_job(job_id: int) -> JobInfo:
    return await _snapshot(_get_record(job_id))


async def get_all_jobs() -> list[JobInfo]:
    async with _jobs_lock:
        records = list(_jobs.values())
    return [await _snapshot(record) for record in records]


async def cancel_job(job_id: int) -> JobInfo:
    record = _get_record(job_id)
    async with record.lock:
        record.cancel_requested = True
        if record.info.job_status == JobStatus.PENDING:
            record.info.job_status = JobStatus.FINISHED
            for index in range(len(record.info.sources_statuses)):
                if record.info.sources_statuses[index] == SourceStatus.PENDING:
                    record.info.sources_statuses[index] = SourceStatus.FINISHED
    task = record.task
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return await _snapshot(record)
