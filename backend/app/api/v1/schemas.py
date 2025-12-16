from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

GameStatus = Literal["in_progress", "player_won", "computer_won", "draw"]
Turn = Literal["player", "computer"]


class PromoInfo(BaseModel):
    available: bool
    reason: str | None = None


class CreateGameRequest(BaseModel):
    player_symbol: Literal["X"] = "X"
    first_turn: Turn = "player"


class GameStateResponse(BaseModel):
    game_id: uuid.UUID
    board: str
    status: GameStatus
    next_turn: Turn
    player_symbol: str
    computer_symbol: str
    promo: PromoInfo


class MoveRequest(BaseModel):
    cell: int = Field(ge=0, le=8)


class MoveResponse(BaseModel):
    game_id: uuid.UUID
    board: str
    status: GameStatus
    next_turn: Turn

    player_move: int
    computer_move: int | None

    promo_code: str | None
    promo: PromoInfo
