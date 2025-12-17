from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    CreateGameRequest,
    GameStateResponse,
    MoveRequest,
    MoveResponse,
    PromoInfo,
)
from app.dependencies import get_db_session
from app.domain.tictactoe import Symbol, apply_move, best_computer_move, is_draw, winner_symbol
from app.models import Game, GameStatus, Turn
from app.services.idempotency import (
    compute_request_hash,
    get_idempotent_response,
    save_idempotent_response,
)
from app.services.outbox import enqueue_telegram_message
from app.services.promo import acquire_promo_locks, issue_promo_code, promo_is_available
from app.settings import get_settings

router = APIRouter()


def _computer_move_with_mistake(board: str, computer_symbol: Symbol, player_symbol: Symbol) -> int | None:
    best = best_computer_move(board, computer_symbol, player_symbol)
    if best is None:
        return None

    if random.random() >= 0.25:
        return best

    legal = [i for i, c in enumerate(board) if c == "."]
    alternatives = [m for m in legal if m != best]
    if not alternatives:
        return best
    return random.choice(alternatives)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is None:
        return ""
    host = request.client.host
    if host in {"127.0.0.1", "::1"}:
        return ""
    return host


@router.post("", response_model=GameStateResponse, status_code=status.HTTP_201_CREATED)
async def create_game(
    body: CreateGameRequest,
    request: Request,
    x_client_id: uuid.UUID | None = Header(default=None, alias="X-Client-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> GameStateResponse:
    settings = get_settings()
    promo = PromoInfo(available=True, reason=None)
    if settings.promo_limits_enabled and x_client_id is not None:
        ip = _client_ip(request)
        available, reason = await promo_is_available(session, client_id=x_client_id, ip=ip)
        promo = PromoInfo(available=available, reason=reason)

    game = Game(
        status=GameStatus.in_progress,
        board=".........",
        next_turn=Turn(body.first_turn),
        player_symbol=body.player_symbol,
        computer_symbol="O",
        move_count=0,
    )

    if game.next_turn == Turn.computer:
        cm = _computer_move_with_mistake(
            game.board,
            cast(Symbol, game.computer_symbol),
            cast(Symbol, game.player_symbol),
        )
        if cm is not None:
            game.board = apply_move(game.board, cm, cast(Symbol, game.computer_symbol))
            game.move_count = int(game.move_count) + 1
        game.next_turn = Turn.player

    session.add(game)
    await session.commit()

    return GameStateResponse(
        game_id=game.id,
        board=game.board,
        status=game.status.value,
        next_turn=game.next_turn.value,
        player_symbol=game.player_symbol,
        computer_symbol=game.computer_symbol,
        promo=promo,
    )


@router.get("/{game_id}", response_model=GameStateResponse)
async def get_game(
    game_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> GameStateResponse:
    row = await session.execute(select(Game).where(Game.id == game_id))
    game = row.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")

    promo = PromoInfo(available=True, reason=None)
    return GameStateResponse(
        game_id=game.id,
        board=game.board,
        status=game.status.value,
        next_turn=game.next_turn.value,
        player_symbol=game.player_symbol,
        computer_symbol=game.computer_symbol,
        promo=promo,
    )


@router.post("/{game_id}/moves", response_model=MoveResponse)
async def make_move(
    request: Request,
    game_id: uuid.UUID,
    body: MoveRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_client_id: uuid.UUID = Header(alias="X-Client-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> MoveResponse:
    settings = get_settings()
    ip = _client_ip(request)

    request_hash = compute_request_hash(str(game_id), str(body.cell), str(x_client_id))

    async with session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
            {"k": f"idempotency:{idempotency_key}"},
        )

        try:
            cached = await get_idempotent_response(session, idempotency_key, request_hash)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        if cached is not None:
            return MoveResponse.model_validate(cached)

        row = await session.execute(select(Game).where(Game.id == game_id).with_for_update())
        game = row.scalar_one_or_none()
        if game is None:
            raise HTTPException(status_code=404, detail="game not found")

        if game.status != GameStatus.in_progress:
            raise HTTPException(status_code=409, detail="game finished")
        if game.next_turn != Turn.player:
            raise HTTPException(status_code=409, detail="not your turn")

        try:
            game.board = apply_move(game.board, body.cell, cast(Symbol, game.player_symbol))
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

        game.move_count = int(game.move_count) + 1

        player_move = body.cell
        computer_move: int | None = None

        w = winner_symbol(game.board)
        if w == game.player_symbol:
            game.status = GameStatus.player_won
        elif is_draw(game.board):
            game.status = GameStatus.draw
        else:
            cm = _computer_move_with_mistake(
                game.board,
                cast(Symbol, game.computer_symbol),
                cast(Symbol, game.player_symbol),
            )
            if cm is None:
                game.status = GameStatus.draw
            else:
                game.board = apply_move(game.board, cm, cast(Symbol, game.computer_symbol))
                computer_move = cm
                game.move_count = int(game.move_count) + 1

                w2 = winner_symbol(game.board)
                if w2 == game.computer_symbol:
                    game.status = GameStatus.computer_won
                elif is_draw(game.board):
                    game.status = GameStatus.draw
                else:
                    game.status = GameStatus.in_progress

        promo_code: str | None = None
        promo = PromoInfo(available=True, reason=None)

        game.next_turn = Turn.player
        if game.status != GameStatus.in_progress:
            game.finished_at = datetime.now(timezone.utc)

        if game.status == GameStatus.player_won:
            if settings.promo_limits_enabled:
                await acquire_promo_locks(session, client_id=x_client_id, ip=ip)
                available, reason = await promo_is_available(session, client_id=x_client_id, ip=ip)
                promo = PromoInfo(available=available, reason=reason)
                if available:
                    promo_code, promo_id = await issue_promo_code(
                        session, game_id=game.id, client_id=x_client_id, ip=ip
                    )
                    game.promo_code_id = promo_id
            else:
                promo_code, promo_id = await issue_promo_code(
                    session, game_id=game.id, client_id=x_client_id, ip=ip
                )
                game.promo_code_id = promo_id

            if settings.telegram_bot_token and settings.telegram_chat_id:
                text_msg = (
                    f"Победа! Промокод выдан: {promo_code}"
                    if promo_code is not None
                    else "Победа! Промокод не выдан: daily_limit"
                )
                await enqueue_telegram_message(
                    session,
                    dedupe_key=f"telegram:game:{game.id}:player_won",
                    chat_id=settings.telegram_chat_id,
                    text=text_msg,
                    metadata={"game_id": str(game.id)},
                )

        if game.status == GameStatus.computer_won:
            if settings.telegram_bot_token and settings.telegram_chat_id:
                await enqueue_telegram_message(
                    session,
                    dedupe_key=f"telegram:game:{game.id}:computer_won",
                    chat_id=settings.telegram_chat_id,
                    text="Проигрыш",
                    metadata={"game_id": str(game.id)},
                )

        response = MoveResponse(
            game_id=game.id,
            board=game.board,
            status=game.status.value,
            next_turn=game.next_turn.value,
            player_move=player_move,
            computer_move=computer_move,
            promo_code=promo_code,
            promo=promo,
        )

        await save_idempotent_response(
            session,
            idempotency_key,
            request_hash,
            response.model_dump(mode="json"),
        )

        return response
