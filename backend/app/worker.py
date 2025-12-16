from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import create_engine, create_sessionmaker
from app.logging_setup import configure_logging, log_event
from app.models import OutboxEvent, OutboxStatus
from app.settings import get_settings

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _retry_delay_seconds(attempts: int) -> int:
    if attempts <= 0:
        return 60
    if attempts == 1:
        return 60
    if attempts == 2:
        return 300
    return 1800


async def _send_telegram_message(
    client: httpx.AsyncClient, token: str, chat_id: str, text_msg: str
) -> None:
    resp = await client.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text_msg},
        timeout=10.0,
    )
    resp.raise_for_status()


async def _requeue_stale_processing(session: AsyncSession, timeout_seconds: float) -> int:
    cutoff = _now_utc() - timedelta(seconds=timeout_seconds)
    stmt = (
        update(OutboxEvent)
        .where(
            (OutboxEvent.status == OutboxStatus.processing)
            & (OutboxEvent.locked_at.is_not(None))
            & (OutboxEvent.locked_at < cutoff)
        )
        .values(status=OutboxStatus.pending, locked_at=None, locked_by=None)
    )
    res = await session.execute(stmt)
    return int(res.rowcount or 0)


async def _claim_batch(session: AsyncSession, batch_size: int, worker_id: str) -> list[OutboxEvent]:
    now = _now_utc()
    stmt = (
        select(OutboxEvent)
        .where(
            (OutboxEvent.status.in_([OutboxStatus.pending, OutboxStatus.failed]))
            & (OutboxEvent.next_retry_at <= now)
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rows = await session.execute(stmt)
    events = list(rows.scalars().all())
    for ev in events:
        ev.status = OutboxStatus.processing
        ev.locked_at = now
        ev.locked_by = worker_id
    return events


async def _mark_sent(session: AsyncSession, event_id: uuid.UUID, worker_id: str) -> None:
    await session.execute(
        update(OutboxEvent)
        .where(
            (OutboxEvent.id == event_id)
            & (OutboxEvent.status == OutboxStatus.processing)
            & (OutboxEvent.locked_by == worker_id)
        )
        .values(status=OutboxStatus.sent, locked_at=None, locked_by=None)
    )


async def _mark_failed(
    session: AsyncSession, event: OutboxEvent, worker_id: str, error: str
) -> None:
    next_attempts = int(event.attempts) + 1
    delay = _retry_delay_seconds(next_attempts)
    next_retry_at = _now_utc() + timedelta(seconds=delay)
    await session.execute(
        update(OutboxEvent)
        .where(
            (OutboxEvent.id == event.id)
            & (OutboxEvent.status == OutboxStatus.processing)
            & (OutboxEvent.locked_by == worker_id)
        )
        .values(
            status=OutboxStatus.failed,
            attempts=next_attempts,
            next_retry_at=next_retry_at,
            locked_at=None,
            locked_by=None,
        )
    )
    log_event(logger, "outbox_failed", event_id=str(event.id), attempts=next_attempts, error=error)


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    worker_id = os.getenv("WORKER_ID") or f"{socket.gethostname()}:{uuid.uuid4()}"

    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)

    log_event(logger, "worker_start", worker_id=worker_id)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            while True:
                async with sessionmaker() as session:
                    async with session.begin():
                        await _requeue_stale_processing(
                            session, settings.outbox_processing_timeout_seconds
                        )

                    async with session.begin():
                        events = await _claim_batch(session, settings.outbox_batch_size, worker_id)

                if not events:
                    await asyncio.sleep(settings.outbox_poll_interval_seconds)
                    continue

                for ev in events:
                    try:
                        if ev.event_type != "telegram_message":
                            async with sessionmaker() as session:
                                async with session.begin():
                                    await _mark_failed(
                                        session, ev, worker_id, "unsupported_event_type"
                                    )
                            continue

                        payload = ev.payload
                        chat_id = str(payload.get("chat_id", ""))
                        text_msg = str(payload.get("text", ""))
                        if not settings.telegram_bot_token or not chat_id or not text_msg:
                            async with sessionmaker() as session:
                                async with session.begin():
                                    await _mark_failed(
                                        session, ev, worker_id, "telegram_not_configured"
                                    )
                            continue

                        await _send_telegram_message(
                            client, settings.telegram_bot_token, chat_id, text_msg
                        )

                        async with sessionmaker() as session:
                            async with session.begin():
                                await _mark_sent(session, ev.id, worker_id)

                        log_event(logger, "outbox_sent", event_id=str(ev.id))

                    except Exception as e:
                        async with sessionmaker() as session:
                            async with session.begin():
                                await _mark_failed(session, ev, worker_id, str(e))

        finally:
            await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
