from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from alembic import command
from alembic.config import Config
from app.main import create_app


def _alembic_config() -> Config:
    base_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(base_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(base_dir / "alembic"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _require_test_env() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required for tests")
    if not os.getenv("ALEMBIC_DATABASE_URL"):
        raise RuntimeError("ALEMBIC_DATABASE_URL is required for tests")


@pytest.fixture(scope="session", autouse=True)
def _migrate_db() -> None:
    command.upgrade(_alembic_config(), "head")


@pytest_asyncio.fixture()
async def app():
    app = create_app()
    async with LifespanManager(app):
        sessionmaker = app.state.sessionmaker
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "TRUNCATE TABLE outbox_events, promo_codes, idempotency_keys, games "
                        "RESTART IDENTITY CASCADE"
                    )
                )
        yield app


@pytest_asyncio.fixture()
async def app_with_telegram(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    app = create_app()
    async with LifespanManager(app):
        sessionmaker = app.state.sessionmaker
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "TRUNCATE TABLE outbox_events, promo_codes, idempotency_keys, games "
                        "RESTART IDENTITY CASCADE"
                    )
                )
        yield app


@pytest_asyncio.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture()
async def client_with_telegram(app_with_telegram):
    transport = ASGITransport(app=app_with_telegram)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
