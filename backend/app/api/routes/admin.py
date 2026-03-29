"""
GoatRaw — Admin API Routes
Protected by admin role. Access: /admin/*
Provides: user management, system health, task oversight, billing overview.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.redis_client import get_redis
from app.api.deps import get_current_user

logger = logging.getLogger("goatraw.admin")
router = APIRouter()

# ── Admin guard ───────────────────────────────────────────────

ADMIN_EMAILS = set(filter(None, __import__("os").getenv("ADMIN_EMAILS", "").split(",")))


async def require_admin(user=Depends(get_current_user)) -> dict:
    """Only allow requests from configured admin email addresses."""
    email = user.get("email", "")
    if ADMIN_EMAILS and email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


# ── System Stats ──────────────────────────────────────────────

@router.get("/stats")
async def system_stats(_=Depends(require_admin)):
    """Overall system health and usage metrics."""
    r    = get_redis()
    now  = datetime.utcnow()
    keys = await r.keys("goatraw:usage:*")

    total_tasks = 0
    total_steps = 0
    monthly     = {}

    for key in keys:
        raw = await r.hgetall(key)
        tc  = int(raw.get("task_count", 0))
        sc  = int(raw.get("step_count", 0))
        total_tasks += tc
        total_steps += sc
        # Extract month from key: goatraw:usage:{user_id}:{YYYYMM}
        parts = key.split(":")
        if len(parts) >= 4:
            month = parts[-1]
            monthly[month] = monthly.get(month, 0) + tc

    # Active websocket connections
    from app.api.routes.websocket import manager
    ws_stats = {"active_users": manager.active_users, "active_connections": manager.active_connections}

    # Redis queue depth
    queue_depth   = await r.llen("goatraw:task_queue")
    cron_due      = await r.zcount("goatraw:cron:queue", 0, now.timestamp())
    heartbeat_due = await r.zcount("goatraw:heartbeat:due", 0, now.timestamp())

    return {
        "timestamp":     now.isoformat(),
        "totals": {
            "tasks_all_time": total_tasks,
            "steps_all_time": total_steps,
        },
        "monthly_tasks":  monthly,
        "queue": {
            "pending_tasks":   queue_depth,
            "cron_due":        cron_due,
            "heartbeats_due":  heartbeat_due,
        },
        "websockets":     ws_stats,
    }


@router.get("/users")
async def list_users(
    limit:  int  = Query(50, le=200),
    offset: int  = Query(0),
    plan:   Optional[str] = None,
    _=Depends(require_admin),
):
    """List users with their plan and usage stats."""
    r    = get_redis()
    keys = await r.keys("goatraw:workspace:user:*")
    users = []
    month_key = datetime.utcnow().strftime("%Y%m")

    for key in keys[offset:offset + limit]:
        user_id   = key.split(":")[-1]
        ws_id_raw = await r.get(key)
        if not ws_id_raw:
            continue

        ws_raw = await r.get(f"goatraw:workspace:{ws_id_raw}")
        ws     = json.loads(ws_raw) if ws_raw else {}

        usage_raw = await r.hgetall(f"goatraw:usage:{user_id}:{month_key}")
        plan_raw  = await r.get(f"goatraw:user_plan:{user_id}")
        user_plan = json.loads(plan_raw).get("plan", "free") if plan_raw else "free"

        if plan and user_plan != plan:
            continue

        users.append({
            "user_id":      user_id,
            "workspace_id": ws_id_raw,
            "plan":         user_plan,
            "this_month": {
                "tasks": int(usage_raw.get("task_count", 0)),
                "steps": int(usage_raw.get("step_count", 0)),
            },
            "workspace_name": ws.get("name", ""),
        })

    return {"users": users, "total": len(users), "offset": offset, "limit": limit}


@router.get("/tasks/recent")
async def recent_tasks(limit: int = Query(20, le=100), _=Depends(require_admin)):
    """Get recently completed/failed tasks across all users."""
    r         = get_redis()
    task_keys = await r.keys("goatraw:task_result:*")
    tasks     = []

    for key in task_keys[: limit * 2]:   # over-fetch since some may be empty
        raw = await r.get(key)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            tasks.append({
                "task_id":      data.get("task_id", ""),
                "agent_type":   data.get("agent_type", ""),
                "status":       data.get("status", ""),
                "steps_taken":  data.get("steps_taken", 0),
                "completed_at": data.get("completed_at", ""),
                "goal_preview": (data.get("goal") or "")[:80],
            })
        except Exception:
            pass
        if len(tasks) >= limit:
            break

    tasks.sort(key=lambda t: t.get("completed_at", ""), reverse=True)
    return {"tasks": tasks[:limit], "total": len(tasks)}


@router.get("/revenue")
async def revenue_overview(_=Depends(require_admin)):
    """Revenue metrics by plan tier."""
    r         = get_redis()
    plan_keys = await r.keys("goatraw:user_plan:*")

    counts = {"free": 0, "pro": 0, "enterprise": 0}
    for key in plan_keys:
        raw = await r.get(key)
        if raw:
            plan = json.loads(raw).get("plan", "free")
            counts[plan] = counts.get(plan, 0) + 1

    mrr_inr = counts["pro"] * 2999 + counts["enterprise"] * 14999
    mrr_usd = counts["pro"] * 36   + counts["enterprise"] * 179

    return {
        "users_by_plan": counts,
        "mrr": {
            "inr": mrr_inr,
            "usd": mrr_usd,
            "formatted_inr": f"₹{mrr_inr:,}",
            "formatted_usd": f"${mrr_usd:,}",
        },
        "arr": {
            "inr": mrr_inr * 12,
            "usd": mrr_usd * 12,
        },
    }


@router.post("/users/{user_id}/set-plan")
async def set_user_plan(user_id: str, body: dict, _=Depends(require_admin)):
    """Admin: manually set a user's plan (for trials, comps, etc.)."""
    plan = body.get("plan", "free")
    if plan not in ("free", "pro", "enterprise"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    r = get_redis()
    if plan == "free":
        await r.delete(f"goatraw:user_plan:{user_id}")
    else:
        from app.api.routes.payments import activate_plan
        await activate_plan(user_id, plan)

    logger.info(f"Admin set plan: {user_id} → {plan}")
    return {"user_id": user_id, "plan": plan, "status": "set"}


@router.delete("/users/{user_id}/rate-limit")
async def clear_rate_limit(user_id: str, _=Depends(require_admin)):
    """Admin: clear rate limit counter for a user (unblock them)."""
    r = get_redis()
    await r.delete(f"goatraw:ratelimit:{user_id}")
    return {"user_id": user_id, "status": "rate_limit_cleared"}


@router.get("/queue/drain")
async def queue_stats(_=Depends(require_admin)):
    """Inspect the task queue without draining it."""
    r     = get_redis()
    depth = await r.llen("goatraw:task_queue")
    # Peek at top 5 tasks
    raw_list = await r.lrange("goatraw:task_queue", -5, -1)
    preview  = []
    for raw in raw_list:
        try:
            task = json.loads(raw)
            preview.append({
                "task_id":    task.get("task_id", "")[:12],
                "agent_type": task.get("agent_type", ""),
                "goal":       (task.get("goal") or "")[:60],
            })
        except Exception:
            pass

    return {"queue_depth": depth, "preview": preview}
