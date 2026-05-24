__all__ = ["lifespan"]

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.modules.search.common import close_browser_context
from src.modules.search.rerank import close_rerank_client


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_rerank_client()
    await close_browser_context()
