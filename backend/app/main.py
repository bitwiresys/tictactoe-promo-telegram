from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.responses import Response

from app.api.v1.router import router as v1_router
from app.db import create_engine, create_sessionmaker
from app.logging_setup import configure_logging, set_request_id
from app.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = engine
        app.state.sessionmaker = sessionmaker
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Tic-Tac-Toe API", version="1.0.0", lifespan=lifespan)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    origin_regex = settings.cors_origin_regex.strip() or None
    if origins or origin_regex:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_origin_regex=origin_regex,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        set_request_id(rid)
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        async with sessionmaker() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}

    app.include_router(v1_router)
    return app


app = create_app()
