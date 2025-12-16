from __future__ import annotations

from functools import lru_cache
from typing import Literal, cast

Symbol = Literal["X", "O"]

_WIN_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


def validate_board(board: str) -> None:
    if len(board) != 9:
        raise ValueError("board must have length 9")
    for ch in board:
        if ch not in {".", "X", "O"}:
            raise ValueError("board contains invalid characters")


def winner_symbol(board: str) -> Symbol | None:
    validate_board(board)
    for a, b, c in _WIN_LINES:
        if board[a] != "." and board[a] == board[b] == board[c]:
            return cast(Symbol, board[a])
    return None


def winning_line(board: str) -> tuple[int, int, int] | None:
    validate_board(board)
    for a, b, c in _WIN_LINES:
        if board[a] != "." and board[a] == board[b] == board[c]:
            return (a, b, c)
    return None


def is_draw(board: str) -> bool:
    validate_board(board)
    return winner_symbol(board) is None and "." not in board


def apply_move(board: str, cell: int, symbol: Symbol) -> str:
    validate_board(board)
    if cell < 0 or cell > 8:
        raise ValueError("cell must be in 0..8")
    if board[cell] != ".":
        raise ValueError("cell is not empty")
    return board[:cell] + symbol + board[cell + 1 :]


def available_moves(board: str) -> list[int]:
    validate_board(board)
    return [i for i, ch in enumerate(board) if ch == "."]


@lru_cache(maxsize=100_000)
def _minimax(board: str, computer: Symbol, player: Symbol, turn: Symbol) -> int:
    w = winner_symbol(board)
    if w == computer:
        return 1
    if w == player:
        return -1
    if "." not in board:
        return 0

    moves = available_moves(board)
    if turn == computer:
        best = -2
        for m in moves:
            score = _minimax(apply_move(board, m, computer), computer, player, player)
            if score > best:
                best = score
                if best == 1:
                    break
        return best

    best = 2
    for m in moves:
        score = _minimax(apply_move(board, m, player), computer, player, computer)
        if score < best:
            best = score
            if best == -1:
                break
    return best


def best_computer_move(board: str, computer: Symbol, player: Symbol) -> int | None:
    validate_board(board)
    if winner_symbol(board) is not None or "." not in board:
        return None

    best_score = -2
    best_move: int | None = None
    for m in available_moves(board):
        score = _minimax(apply_move(board, m, computer), computer, player, player)
        if score > best_score:
            best_score = score
            best_move = m
        elif score == best_score and best_move is not None and m < best_move:
            best_move = m

    return best_move
