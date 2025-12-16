from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxEvent, OutboxStatus


async def enqueue_telegram_message(
    session: AsyncSession,
    *,
    dedupe_key: str,
    chat_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if metadata:
        payload["metadata"] = metadata

    stmt = (
        insert(OutboxEvent)
        .values(
            id=uuid.uuid4(),
            event_type="telegram_message",
            dedupe_key=dedupe_key,
            payload=payload,
            status=OutboxStatus.pending,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
    await session.execute(stmt)
