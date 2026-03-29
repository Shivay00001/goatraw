"""
GoatRaw - API Dependencies & Auth
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime
from app.core.config import settings
from app.core.redis_client import check_rate_limit

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Decode JWT and return user payload."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


async def check_rate_limit_for_user(user: dict) -> None:
    """Enforce per-plan rate limits."""
    plan = user.get("plan", "free")
    limits = {
        "free": settings.RATE_LIMIT_FREE,
        "pro": settings.RATE_LIMIT_PRO,
        "enterprise": settings.RATE_LIMIT_ENTERPRISE,
    }
    limit = limits.get(plan, settings.RATE_LIMIT_FREE)
    user_id = str(user.get("id", ""))
    allowed = await check_rate_limit(user_id, limit)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Your {plan} plan allows {limit} requests/hour.",
        )
