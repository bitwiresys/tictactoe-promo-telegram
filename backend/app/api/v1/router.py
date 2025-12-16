from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.games import router as games_router
from app.api.v1.health import router as health_router

router = APIRouter(prefix="/api/v1")

router.include_router(health_router)
router.include_router(games_router, prefix="/games", tags=["games"])
