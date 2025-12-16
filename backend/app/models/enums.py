from __future__ import annotations

import enum


class GameStatus(str, enum.Enum):
    in_progress = "in_progress"
    player_won = "player_won"
    computer_won = "computer_won"
    draw = "draw"


class Turn(str, enum.Enum):
    player = "player"
    computer = "computer"


class OutboxStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    sent = "sent"
    failed = "failed"
