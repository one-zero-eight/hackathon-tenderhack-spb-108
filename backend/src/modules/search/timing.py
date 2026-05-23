"""Wall-clock timing helpers for search pipeline stages."""

import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Self

from src.modules.search.schemas import ProductTiming, RequestTiming, SourceTiming, StageTiming


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(dt: datetime) -> str:
    return dt.isoformat()


class TimingRecorder:
    def __init__(self) -> None:
        self._started_perf = time.perf_counter()
        self._started_at = utc_now()
        self.stages: list[StageTiming] = []

    @classmethod
    def start(cls) -> Self:
        return cls()

    @property
    def started_at(self) -> str:
        return to_iso(self._started_at)

    @property
    def duration_ms(self) -> float:
        return (time.perf_counter() - self._started_perf) * 1000

    def ended_at(self) -> str:
        return to_iso(utc_now())

    def add_stage(self, name: str, duration_ms: float, started_at: datetime, ended_at: datetime) -> None:
        self.stages.append(
            StageTiming(
                name=name,
                duration_ms=round(duration_ms, 2),
                started_at=to_iso(started_at),
                ended_at=to_iso(ended_at),
            )
        )

    @asynccontextmanager
    async def stage(self, name: str):
        started_at = utc_now()
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.add_stage(name, (time.perf_counter() - t0) * 1000, started_at, utc_now())

    def to_product_timing(self) -> ProductTiming:
        ended = utc_now()
        return ProductTiming(
            duration_ms=round(self.duration_ms, 2),
            started_at=self.started_at,
            ended_at=to_iso(ended),
            stages=self.stages,
        )

    def to_source_timing(self) -> SourceTiming:
        ended = utc_now()
        return SourceTiming(
            duration_ms=round(self.duration_ms, 2),
            started_at=self.started_at,
            ended_at=to_iso(ended),
            stages=self.stages,
        )

    def to_request_timing(self) -> RequestTiming:
        ended = utc_now()
        return RequestTiming(
            duration_ms=round(self.duration_ms, 2),
            started_at=self.started_at,
            ended_at=to_iso(ended),
            stages=self.stages,
        )
