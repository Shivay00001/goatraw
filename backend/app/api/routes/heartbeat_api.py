"""
GoatRaw - Heartbeat API Routes
GET  /heartbeat/config         — get heartbeat config
POST /heartbeat/config         — save/update heartbeat config
POST /heartbeat/trigger        — manually fire one heartbeat
GET  /heartbeat/history        — last 20 heartbeat results
DELETE /heartbeat/config       — disable heartbeat
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import json

from app.workers.heartbeat import HeartbeatConfig, heartbeat_store, run_heartbeat_for_user
from app.api.deps import get_current_user
from app.core.redis_client import get_redis

router = APIRouter()


class HeartbeatConfigRequest(BaseModel):
    enabled: bool = True
    interval_minutes: int = Field(30, ge=5, le=1440, description="How often to fire (5-1440 min)")
    checklist: List[str] = Field(default=[], description="Items to check each heartbeat")
    notify_channel: str = Field("webhook", description="webhook | telegram | slack | email")
    notify_endpoint: str = Field("", description="Webhook URL or Telegram chat_id")
    silent_ok: bool = Field(True, description="If True, only notify when action needed")


@router.get("/config")
async def get_heartbeat_config(user=Depends(get_current_user)):
    """Get the user's current heartbeat configuration."""
    config = await heartbeat_store.get(str(user["id"]))
    if not config:
        return {
            "configured": False,
            "default": HeartbeatConfig(user_id=str(user["id"])).to_dict(),
        }
    return {"configured": True, "config": config.to_dict()}


@router.post("/config")
async def save_heartbeat_config(body: HeartbeatConfigRequest, user=Depends(get_current_user)):
    """Create or update the heartbeat configuration."""
    config = HeartbeatConfig(
        user_id=str(user["id"]),
        enabled=body.enabled,
        interval_minutes=body.interval_minutes,
        checklist=body.checklist,
        notify_channel=body.notify_channel,
        notify_endpoint=body.notify_endpoint,
        silent_ok=body.silent_ok,
    )
    await heartbeat_store.save(config)
    return {
        "status": "saved",
        "enabled": config.enabled,
        "interval_minutes": config.interval_minutes,
        "checklist_items": len(config.checklist),
    }


@router.post("/trigger")
async def trigger_heartbeat(user=Depends(get_current_user)):
    """Manually fire one heartbeat cycle right now."""
    result = await run_heartbeat_for_user(str(user["id"]))
    return {"status": "fired", "result": result}


@router.get("/history")
async def heartbeat_history(user=Depends(get_current_user)):
    """Get recent heartbeat results."""
    r = get_redis()
    hist_key = f"goatraw:heartbeat:history:{user['id']}"
    raw_list = await r.lrange(hist_key, 0, 19)
    history = [json.loads(x) for x in raw_list]
    return {"history": history, "count": len(history)}


@router.delete("/config")
async def disable_heartbeat(user=Depends(get_current_user)):
    """Disable the heartbeat for this user."""
    config = await heartbeat_store.get(str(user["id"]))
    if config:
        config.enabled = False
        await heartbeat_store.save(config)
    return {"status": "disabled"}
