"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.retrieval import router as retrieval_router
from app.config import get_settings
from app.logging import configure_logging
from app.queue.dispatcher import Dispatcher
from app.store.migrations import run_migrations


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    run_migrations(settings)
    dispatcher = Dispatcher(settings)
    dispatcher.start()
    try:
        yield
    finally:
        dispatcher.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="mem0-owui-governance", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(events_router)
    app.include_router(retrieval_router)
    return app


app = create_app()
