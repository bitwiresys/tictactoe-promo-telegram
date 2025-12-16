from __future__ import annotations

import random
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromoCode, PromoIssuanceLimit


async def promo_is_available(
    session: AsyncSession, *, client_id: uuid.UUID, ip: str
) -> tuple[bool, str | None]:
    cutoff = func.now() - text("INTERVAL '24 hours'")

    row = await session.execute(
        select(PromoIssuanceLimit.id).where(
            (PromoIssuanceLimit.client_id == client_id) & (PromoIssuanceLimit.issued_at >= cutoff)
        )
    )
    if row.first() is not None:
        return False, "daily_limit"

    if ip:
        row = await session.execute(
            select(PromoIssuanceLimit.id).where(
                (PromoIssuanceLimit.ip == ip) & (PromoIssuanceLimit.issued_at >= cutoff)
            )
        )
        if row.first() is not None:
            return False, "daily_limit"

    return True, None


async def acquire_promo_locks(session: AsyncSession, *, client_id: uuid.UUID, ip: str) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"promo:client:{client_id}"}
    )
    if ip:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"promo:ip:{ip}"}
        )


def _generate_code(rng: random.Random) -> str:
    return str(rng.randint(10000, 99999))


async def issue_promo_code(
    session: AsyncSession,
    *,
    game_id: uuid.UUID,
    client_id: uuid.UUID,
    ip: str,
    rng: random.Random | None = None,
) -> tuple[str, uuid.UUID]:
    r = rng or random.SystemRandom()

    for _ in range(20):
        code = _generate_code(r)
        async with session.begin_nested():
            promo = PromoCode(code=code, game_id=game_id)
            session.add(promo)
            try:
                await session.flush()
            except IntegrityError:
                continue

            session.add(PromoIssuanceLimit(client_id=client_id, ip=ip))
            return code, promo.id

    raise RuntimeError("Failed to generate unique promo code")
