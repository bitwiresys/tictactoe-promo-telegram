from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyKey


def compute_request_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


async def get_idempotent_response(
    session: AsyncSession, key: str, request_hash: str
) -> dict[str, Any] | None:
    row = await session.execute(select(IdempotencyKey).where(IdempotencyKey.key == key))
    idem = row.scalar_one_or_none()
    if idem is None:
        return None
    if idem.request_hash != request_hash:
        raise ValueError("Idempotency key reuse with different payload")
    return dict(idem.response)


async def save_idempotent_response(
    session: AsyncSession, key: str, request_hash: str, response: dict[str, Any]
) -> None:
    session.add(IdempotencyKey(key=key, request_hash=request_hash, response=response))
