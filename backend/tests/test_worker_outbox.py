from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import OutboxEvent, OutboxStatus
from app.worker import _claim_batch, _mark_failed, _mark_sent, _requeue_stale_processing


@pytest.mark.asyncio
async def test_worker_claim_mark_sent(app) -> None:
    sessionmaker = app.state.sessionmaker

    event_id = uuid.uuid4()
    async with sessionmaker() as session:
        async with session.begin():
            session.add(
                OutboxEvent(
                    id=event_id,
                    event_type="telegram_message",
                    dedupe_key=f"k:{event_id}",
                    payload={"chat_id": "1", "text": "hi"},
                    status=OutboxStatus.pending,
                    attempts=0,
                    next_retry_at=datetime.now(timezone.utc),
                )
            )

    worker_id = "w1"
    async with sessionmaker() as session:
        async with session.begin():
            events = await _claim_batch(session, 10, worker_id)
            assert len(events) == 1
            assert events[0].id == event_id

    async with sessionmaker() as session:
        async with session.begin():
            await _mark_sent(session, event_id, worker_id)

    async with sessionmaker() as session:
        row = await session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
        ev = row.scalar_one()
        assert ev.status == OutboxStatus.sent


@pytest.mark.asyncio
async def test_worker_mark_failed_sets_next_retry(app) -> None:
    sessionmaker = app.state.sessionmaker
    event_id = uuid.uuid4()

    async with sessionmaker() as session:
        async with session.begin():
            session.add(
                OutboxEvent(
                    id=event_id,
                    event_type="telegram_message",
                    dedupe_key=f"k:{event_id}",
                    payload={"chat_id": "1", "text": "hi"},
                    status=OutboxStatus.processing,
                    attempts=0,
                    next_retry_at=datetime.now(timezone.utc),
                    locked_at=datetime.now(timezone.utc),
                    locked_by="w2",
                )
            )

    async with sessionmaker() as session:
        async with session.begin():
            row = await session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
            ev = row.scalar_one()
            await _mark_failed(session, ev, "w2", "boom")

    async with sessionmaker() as session:
        row = await session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
        ev2 = row.scalar_one()
        assert ev2.status == OutboxStatus.failed
        assert int(ev2.attempts) == 1
        assert ev2.next_retry_at >= datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_worker_requeue_stale_processing(app) -> None:
    sessionmaker = app.state.sessionmaker
    event_id = uuid.uuid4()

    async with sessionmaker() as session:
        async with session.begin():
            session.add(
                OutboxEvent(
                    id=event_id,
                    event_type="telegram_message",
                    dedupe_key=f"k:{event_id}",
                    payload={"chat_id": "1", "text": "hi"},
                    status=OutboxStatus.processing,
                    attempts=0,
                    next_retry_at=datetime.now(timezone.utc),
                    locked_at=datetime.now(timezone.utc) - timedelta(seconds=1000),
                    locked_by="w3",
                )
            )

    async with sessionmaker() as session:
        async with session.begin():
            n = await _requeue_stale_processing(session, timeout_seconds=60)
            assert n == 1

    async with sessionmaker() as session:
        row = await session.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))
        ev = row.scalar_one()
        assert ev.status == OutboxStatus.pending
        assert ev.locked_by is None
        assert ev.locked_at is None
