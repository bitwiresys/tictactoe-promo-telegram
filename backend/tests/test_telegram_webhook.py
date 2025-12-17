from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models import OutboxEvent


async def test_telegram_start_creates_outbox(app, client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")

    payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "chat": {"id": 7042270749, "type": "private"},
            "text": "/start",
        },
    }

    r = await client.post("/api/v1/telegram/webhook", json=payload)
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    sessionmaker = app.state.sessionmaker
    async with sessionmaker() as session:
        outbox = await session.execute(
            select(OutboxEvent).where(OutboxEvent.dedupe_key == "telegram:webhook:1:start")
        )
        ev = outbox.scalar_one_or_none()
        assert ev is not None
        assert ev.payload["chat_id"] == "7042270749"
