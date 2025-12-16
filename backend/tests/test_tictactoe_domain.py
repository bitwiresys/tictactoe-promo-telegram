from __future__ import annotations

from app.domain.tictactoe import apply_move, best_computer_move, is_draw, winner_symbol


def test_winner_detection_rows() -> None:
    assert winner_symbol("XXX......") == "X"
    assert winner_symbol("...OOO...") == "O"


def test_draw_detection() -> None:
    board = "XOXOOXXXO"
    assert winner_symbol(board) is None
    assert is_draw(board) is True


def test_computer_blocks_immediate_loss() -> None:
    board = "XX......."
    move = best_computer_move(board, computer="O", player="X")
    assert move == 2


def test_computer_takes_winning_move() -> None:
    board = "OO......."
    move = best_computer_move(board, computer="O", player="X")
    assert move == 2


def test_apply_move_rejects_occupied_cell() -> None:
    board = "X........"
    try:
        apply_move(board, 0, "O")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
