from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models import OutboxEvent


async def test_telegram_start_creates_outbox(app_with_telegram, client_with_telegram: AsyncClient) -> None:

    payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "chat": {"id": 7042270749, "type": "private"},
            "text": "/start",
        },
    }

    r = await client_with_telegram.post("/api/v1/telegram/webhook", json=payload)
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    sessionmaker = app_with_telegram.state.sessionmaker
    async with sessionmaker() as session:
        outbox = await session.execute(
            select(OutboxEvent).where(OutboxEvent.dedupe_key == "telegram:webhook:1:start")
        )
        ev = outbox.scalar_one_or_none()
        assert ev is not None
        assert ev.payload["chat_id"] == "7042270749"
