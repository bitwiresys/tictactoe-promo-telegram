from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import GameStatus, Turn


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (Index("ix_games_finished_at", "finished_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    status: Mapped[GameStatus] = mapped_column(
        SAEnum(GameStatus, name="game_status"), nullable=False, index=True
    )
    board: Mapped[str] = mapped_column(Text, nullable=False)
    next_turn: Mapped[Turn] = mapped_column(SAEnum(Turn, name="turn"), nullable=False)

    player_symbol: Mapped[str] = mapped_column(String(1), nullable=False, default="X")
    computer_symbol: Mapped[str] = mapped_column(String(1), nullable=False, default="O")

    move_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    promo_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("promo_codes.id", use_alter=True, name="fk_games_promo_code_id"),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
