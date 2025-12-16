from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def get_db_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    sessionmaker = getattr(request.app.state, "sessionmaker", None)
    if sessionmaker is None:
        raise RuntimeError("Database sessionmaker is not initialized")
    return cast(async_sessionmaker[AsyncSession], sessionmaker)


async def get_db_session(
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_db_sessionmaker),
) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session
