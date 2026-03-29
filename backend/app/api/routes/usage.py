"""
GoatRaw - Usage & Billing API Routes
GET /usage/current             — current month usage stats
GET /usage/history             — monthly usage history
GET /usage/limits              — plan limits and current status
POST /usage/upgrade            — upgrade plan tier
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json

from app.api.deps import get_current_user
from app.core.redis_client import get_redis
from app.core.config import settings

router = APIRouter()

PLAN_LIMITS = {
    "free": {
        "tasks_per_hour": 10,
        "tasks_per_month": 100,
        "memory_facts": 50,
        "cron_jobs": 2,
        "channels": 1,
        "skills": 5,
        "price_inr": 0,
        "price_usd": 0,
    },
    "pro": {
        "tasks_per_hour": 100,
        "tasks_per_month": 2000,
        "memory_facts": 500,
        "cron_jobs": 20,
        "channels": 5,
        "skills": 50,
        "price_inr": 2999,
        "price_usd": 36,
    },
    "enterprise": {
        "tasks_per_hour": 1000,
        "tasks_per_month": -1,       # unlimited
        "memory_facts": -1,
        "cron_jobs": -1,
        "channels": -1,
        "skills": -1,
        "price_inr": 14999,
        "price_usd": 179,
    },
}


@router.get("/current")
async def get_current_usage(user=Depends(get_current_user)):
    """Get current month usage statistics."""
    r = get_redis()
    user_id = str(user["id"])
    month_key = datetime.utcnow().strftime("%Y%m")
    usage_key = f"goatraw:usage:{user_id}:{month_key}"

    raw = await r.hgetall(usage_key)
    task_count = int(raw.get("task_count", 0))
    step_count = int(raw.get("step_count", 0))
    token_count = int(raw.get("token_count", 0))

    # Estimated cost (Groq is nearly free, OpenAI ~$0.15/1M tokens)
    estimated_cost_usd = round(token_count * 0.00000015, 4)

    return {
        "period": f"{datetime.utcnow().strftime('%B %Y')}",
        "user_id": user_id,
        "plan": user.get("plan", "free"),
        "usage": {
            "tasks_completed": task_count,
            "steps_executed": step_count,
            "tokens_used": token_count,
            "estimated_cost_usd": estimated_cost_usd,
        },
    }


@router.get("/history")
async def get_usage_history(months: int = 3, user=Depends(get_current_user)):
    """Get usage history for last N months."""
    r = get_redis()
    user_id = str(user["id"])
    history = []

    for i in range(months):
        from datetime import timedelta
        dt = datetime.utcnow().replace(day=1) - timedelta(days=i * 28)
        month_key = dt.strftime("%Y%m")
        usage_key = f"goatraw:usage:{user_id}:{month_key}"
        raw = await r.hgetall(usage_key)
        history.append({
            "period": dt.strftime("%B %Y"),
            "month_key": month_key,
            "tasks": int(raw.get("task_count", 0)),
            "steps": int(raw.get("step_count", 0)),
            "tokens": int(raw.get("token_count", 0)),
        })

    return {"history": history}


@router.get("/limits")
async def get_plan_limits(user=Depends(get_current_user)):
    """Get plan limits and current consumption vs limit."""
    r = get_redis()
    user_id = str(user["id"])
    plan = user.get("plan", "free")
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

    # Current month tasks
    month_key = datetime.utcnow().strftime("%Y%m")
    raw = await r.hgetall(f"goatraw:usage:{user_id}:{month_key}")
    tasks_used = int(raw.get("task_count", 0))

    # Current hour tasks (rate limit counter)
    rate_key = f"goatraw:ratelimit:{user_id}"
    tasks_this_hour = int(await r.get(rate_key) or 0)

    return {
        "plan": plan,
        "limits": limits,
        "current": {
            "tasks_this_hour": tasks_this_hour,
            "tasks_this_month": tasks_used,
        },
        "utilization": {
            "hourly": round(tasks_this_hour / max(limits["tasks_per_hour"], 1) * 100, 1),
            "monthly": round(tasks_used / max(limits["tasks_per_month"], 1) * 100, 1) if limits["tasks_per_month"] > 0 else 0,
        },
        "upgrade_available": plan != "enterprise",
    }
