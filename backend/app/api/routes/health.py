"""
GoatRaw - Health Check Route
"""

from fastapi import APIRouter
from app.core.redis_client import get_redis

router = APIRouter()


@router.get("/")
async def health_check():
    """Basic liveness check."""
    return {"status": "ok", "service": "GoatRaw API"}


@router.get("/ready")
async def readiness_check():
    """Readiness check — verifies Redis connectivity."""
    try:
        r = get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "status": "ready" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
    }
