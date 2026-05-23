__all__ = ["lifespan"]

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.modules.search.common import close_browser_context


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_browser_context()
