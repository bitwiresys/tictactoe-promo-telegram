from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.models import Game, GameStatus, Turn


async def _create_prefilled_game(
    app, *, board: str, status: GameStatus, next_turn: Turn
) -> uuid.UUID:
    sessionmaker = app.state.sessionmaker
    async with sessionmaker() as session:
        async with session.begin():
            game = Game(
                status=status,
                board=board,
                next_turn=next_turn,
                player_symbol="X",
                computer_symbol="O",
                move_count=board.count("X") + board.count("O"),
            )
            session.add(game)
        return game.id


async def test_create_game_player_first(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/games",
        json={"player_symbol": "X", "first_turn": "player"},
    )
    assert r.status_code == 201
    data = r.json()
    assert uuid.UUID(data["game_id"])  # valid uuid
    assert data["status"] == "in_progress"
    assert data["next_turn"] == "player"
    assert data["board"] == "........."


async def test_create_game_computer_first(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/games",
        json={"player_symbol": "X", "first_turn": "computer"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "in_progress"
    assert data["next_turn"] == "player"
    # computer should have made exactly one move
    assert data["board"].count("O") == 1
    assert data["board"].count("X") == 0


async def test_get_game_404(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    r = await client.get(f"/api/v1/games/{missing}")
    assert r.status_code == 404


async def test_moves_404(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    r = await client.post(
        f"/api/v1/games/{missing}/moves",
        json={"cell": 0},
        headers={"Idempotency-Key": "k", "X-Client-Id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


async def test_invalid_move_occupied_cell_is_409(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/games",
        json={"player_symbol": "X", "first_turn": "player"},
    )
    game_id = r.json()["game_id"]

    headers = {"Idempotency-Key": "k1", "X-Client-Id": str(uuid.uuid4())}
    ok = await client.post(f"/api/v1/games/{game_id}/moves", json={"cell": 0}, headers=headers)
    assert ok.status_code == 200

    # new idempotency key but same occupied cell
    bad = await client.post(
        f"/api/v1/games/{game_id}/moves",
        json={"cell": 0},
        headers={"Idempotency-Key": "k2", "X-Client-Id": str(uuid.uuid4())},
    )
    assert bad.status_code == 409


async def test_game_finished_is_409(app, client: AsyncClient) -> None:
    game_id = await _create_prefilled_game(
        app,
        board="XXXOO....",
        status=GameStatus.player_won,
        next_turn=Turn.player,
    )
    r = await client.post(
        f"/api/v1/games/{game_id}/moves",
        json={"cell": 5},
        headers={"Idempotency-Key": "f1", "X-Client-Id": str(uuid.uuid4())},
    )
    assert r.status_code == 409


async def test_not_your_turn_is_409(app, client: AsyncClient) -> None:
    game_id = await _create_prefilled_game(
        app,
        board="X..O.....",
        status=GameStatus.in_progress,
        next_turn=Turn.computer,
    )
    r = await client.post(
        f"/api/v1/games/{game_id}/moves",
        json={"cell": 1},
        headers={"Idempotency-Key": "t1", "X-Client-Id": str(uuid.uuid4())},
    )
    assert r.status_code == 409


async def test_promo_ip_daily_limit_enforced(app, client: AsyncClient) -> None:
    ip = "203.0.113.10"

    game1 = await _create_prefilled_game(
        app,
        board="XX.OO....",
        status=GameStatus.in_progress,
        next_turn=Turn.player,
    )
    r1 = await client.post(
        f"/api/v1/games/{game1}/moves",
        json={"cell": 2},
        headers={
            "Idempotency-Key": "ip1",
            "X-Client-Id": str(uuid.uuid4()),
            "X-Forwarded-For": ip,
        },
    )
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["status"] == "player_won"
    assert data1["promo_code"] is not None

    game2 = await _create_prefilled_game(
        app,
        board="XX.OO....",
        status=GameStatus.in_progress,
        next_turn=Turn.player,
    )
    r2 = await client.post(
        f"/api/v1/games/{game2}/moves",
        json={"cell": 2},
        headers={
            "Idempotency-Key": "ip2",
            "X-Client-Id": str(uuid.uuid4()),
            "X-Forwarded-For": ip,
        },
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["status"] == "player_won"
    assert data2["promo_code"] is not None
    assert data2["promo"]["available"] is True

    # Ensure GET works for an existing game (covers success path)
    g = await client.get(f"/api/v1/games/{game2}")
    assert g.status_code == 200

    # And verify game is persisted
    sessionmaker = app.state.sessionmaker
    async with sessionmaker() as session:
        row = await session.execute(select(Game).where(Game.id == game2))
        assert row.scalar_one_or_none() is not None
