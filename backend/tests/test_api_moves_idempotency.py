from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.models import Game, GameStatus, OutboxEvent, Turn


async def _create_prefilled_game(app, *, board: str) -> uuid.UUID:
    sessionmaker = app.state.sessionmaker
    async with sessionmaker() as session:
        async with session.begin():
            game = Game(
                status=GameStatus.in_progress,
                board=board,
                next_turn=Turn.player,
                player_symbol="X",
                computer_symbol="O",
                move_count=board.count("X") + board.count("O"),
            )
            session.add(game)
        return game.id


async def test_idempotency_same_key_returns_same_response(app, client: AsyncClient) -> None:
    r = await client.post("/api/v1/games", json={"player_symbol": "X", "first_turn": "player"})
    assert r.status_code == 201
    game_id = r.json()["game_id"]

    headers = {"Idempotency-Key": "k1", "X-Client-Id": str(uuid.uuid4())}
    r1 = await client.post(f"/api/v1/games/{game_id}/moves", json={"cell": 0}, headers=headers)
    assert r1.status_code == 200
    r2 = await client.post(f"/api/v1/games/{game_id}/moves", json={"cell": 0}, headers=headers)
    assert r2.status_code == 200
    assert r1.json() == r2.json()


async def test_idempotency_reuse_with_different_payload_is_409(app, client: AsyncClient) -> None:
    r = await client.post("/api/v1/games", json={"player_symbol": "X", "first_turn": "player"})
    game_id = r.json()["game_id"]

    client_id = str(uuid.uuid4())
    headers = {"Idempotency-Key": "k2", "X-Client-Id": client_id}
    ok = await client.post(f"/api/v1/games/{game_id}/moves", json={"cell": 0}, headers=headers)
    assert ok.status_code == 200

    bad = await client.post(f"/api/v1/games/{game_id}/moves", json={"cell": 1}, headers=headers)
    assert bad.status_code == 409


async def test_player_win_issues_promo_and_creates_outbox(
    app_with_telegram, client_with_telegram: AsyncClient
) -> None:
    game_id = await _create_prefilled_game(app_with_telegram, board="XX.OO....")

    headers = {
        "Idempotency-Key": "k3",
        "X-Client-Id": str(uuid.uuid4()),
        "X-Telegram-User-Id": "1",
    }
    r = await client_with_telegram.post(
        f"/api/v1/games/{game_id}/moves", json={"cell": 2}, headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "player_won"
    assert data["promo_code"] is not None
    promo_code = data["promo_code"]

    sessionmaker = app_with_telegram.state.sessionmaker
    async with sessionmaker() as session:
        outbox = await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.dedupe_key == f"telegram:game:{game_id}:player_won"
            )
        )
        ev = outbox.scalar_one_or_none()
        assert ev is not None
        assert ev.payload.get("text") == f"Победа! Промокод выдан: {promo_code}"


async def test_computer_win_creates_outbox(
    app_with_telegram, client_with_telegram: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr("random.random", lambda: 1.0)

    game_id = await _create_prefilled_game(app_with_telegram, board="OO.XX....")

    headers = {
        "Idempotency-Key": "k4",
        "X-Client-Id": str(uuid.uuid4()),
        "X-Telegram-User-Id": "1",
    }
    r = await client_with_telegram.post(
        f"/api/v1/games/{game_id}/moves", json={"cell": 8}, headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "computer_won"

    sessionmaker = app_with_telegram.state.sessionmaker
    async with sessionmaker() as session:
        outbox = await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.dedupe_key == f"telegram:game:{game_id}:computer_won"
            )
        )
        ev = outbox.scalar_one_or_none()
        assert ev is not None
        assert ev.payload.get("text") == "Проигрыш"


async def test_promo_daily_limit_blocks_second_code_same_client(app, client: AsyncClient) -> None:
    client_id = uuid.uuid4()

    game1 = await _create_prefilled_game(app, board="XX.OO....")
    r1 = await client.post(
        f"/api/v1/games/{game1}/moves",
        json={"cell": 2},
        headers={"Idempotency-Key": "a1", "X-Client-Id": str(client_id)},
    )
    assert r1.status_code == 200

    game2 = await _create_prefilled_game(app, board="XX.OO....")
    r2 = await client.post(
        f"/api/v1/games/{game2}/moves",
        json={"cell": 2},
        headers={"Idempotency-Key": "a2", "X-Client-Id": str(client_id)},
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["status"] == "player_won"
    assert data2["promo_code"] is not None
    assert data2["promo"]["available"] is True
