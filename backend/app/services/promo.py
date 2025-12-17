from __future__ import annotations

import random
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromoCode


def _generate_code(rng: random.Random) -> str:
    return str(rng.randint(10000, 99999))


async def issue_promo_code(
    session: AsyncSession,
    *,
    game_id: uuid.UUID,
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
            return code, promo.id

    raise RuntimeError("Failed to generate unique promo code")
