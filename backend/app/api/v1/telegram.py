from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.services.outbox import enqueue_telegram_message
from app.settings import get_settings

router = APIRouter(tags=["telegram"])


def _get_chat_id(update: dict[str, Any]) -> str | None:
    message = update.get("message")
    if isinstance(message, dict):
        chat = message.get("chat")
        if isinstance(chat, dict):
            cid = chat.get("id")
            if cid is not None:
                return str(cid)
    return None


def _get_text(update: dict[str, Any]) -> str | None:
    message = update.get("message")
    if isinstance(message, dict):
        text = message.get("text")
        if isinstance(text, str):
            return text
    return None


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        return {"ok": True}

    payload = await request.json()
    if not isinstance(payload, dict):
        return {"ok": True}

    text = _get_text(payload)
    if text is None:
        return {"ok": True}

    if not text.strip().startswith("/start"):
        return {"ok": True}

    chat_id = _get_chat_id(payload)
    if not chat_id:
        return {"ok": True}

    update_id = payload.get("update_id")
    if isinstance(update_id, int):
        dedupe_key = f"telegram:webhook:{update_id}:start"
    else:
        dedupe_key = f"telegram:webhook:{uuid.uuid4()}:start"

    await enqueue_telegram_message(
        session,
        dedupe_key=dedupe_key,
        chat_id=chat_id,
        text="Привет! Игра запущена. Открой мини-приложение и сыграй в крестики-нолики.",
        metadata={"command": "start"},
    )

    return {"ok": True}
