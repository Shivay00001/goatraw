"""
GoatRaw — WebSocket Manager
Real-time task status streaming to the frontend.
Clients connect to ws://.../ws/{user_id} and receive task events.

Events pushed:
  { type: "task_update",  task_id, status }
  { type: "task_result",  task_id, output }
  { type: "heartbeat",    status, message }
  { type: "ping" }
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import jwt

from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger("goatraw.websocket")
router = APIRouter()


# ── Connection Manager ────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections per user."""

    def __init__(self):
        # user_id → set of connected websockets
        self._connections: Dict[str, Set[WebSocket]] = {}
        # task_id → user_id (for routing task events)
        self._task_owners: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(websocket)
        logger.info(f"WS connected: {user_id} ({len(self._connections[user_id])} active)")

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info(f"WS disconnected: {user_id}")

    def register_task(self, task_id: str, user_id: str) -> None:
        self._task_owners[task_id] = user_id

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to all connections for a user."""
        if user_id not in self._connections:
            return
        dead = set()
        for ws in self._connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[user_id].discard(ws)

    async def broadcast_task_update(self, task_id: str, status: str, result=None) -> None:
        """Broadcast a task status change to the task owner."""
        user_id = self._task_owners.get(task_id)
        if not user_id:
            return
        message = {
            "type":      "task_update",
            "task_id":   task_id,
            "status":    status,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if result:
            message["type"]   = "task_result"
            message["output"] = result.get("output")
        await self.send_to_user(user_id, message)

    @property
    def active_users(self) -> int:
        return len(self._connections)

    @property
    def active_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())


manager = ConnectionManager()


# ── Redis pub/sub bridge ──────────────────────────────────────

async def redis_event_listener():
    """
    Listen to Redis pub/sub channel for task events.
    Worker publishes here; WS manager fans out to connected clients.
    """
    from app.core.redis_client import init_redis
    await init_redis()

    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("goatraw:task_events")
    logger.info("Redis event listener started")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data     = json.loads(message["data"])
            task_id  = data.get("task_id")
            status   = data.get("status")
            result   = data.get("result")
            if task_id:
                await manager.broadcast_task_update(task_id, status, result)
        except Exception as e:
            logger.error(f"Redis listener error: {e}")


async def publish_task_event(task_id: str, status: str, result=None) -> None:
    """Called by worker to publish task events to WebSocket clients."""
    try:
        r = get_redis()
        payload = {"task_id": task_id, "status": status}
        if result:
            payload["result"] = result
        await r.publish("goatraw:task_events", json.dumps(payload))
    except Exception as e:
        logger.warning(f"Failed to publish task event: {e}")


# ── JWT verification for WebSocket ────────────────────────────

def decode_ws_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except Exception:
        return None


# ── WebSocket Route ───────────────────────────────────────────

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id:   str,
    token:     str = Query(...),
):
    """
    WebSocket endpoint for real-time updates.
    URL: ws://api/ws/{user_id}?token=JWT_TOKEN
    """
    # Verify token
    payload = decode_ws_token(token)
    if not payload or str(payload.get("id")) != user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, user_id)

    # Send welcome event
    await websocket.send_json({
        "type":    "connected",
        "user_id": user_id,
        "message": "GoatRaw real-time connected",
    })

    try:
        while True:
            # Ping every 30s to keep connection alive
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg  = json.loads(data)

                # Client can register a task_id to track
                if msg.get("type") == "track_task":
                    task_id = msg.get("task_id")
                    if task_id:
                        manager.register_task(task_id, user_id)
                        await websocket.send_json({
                            "type":    "tracking",
                            "task_id": task_id,
                        })

            except asyncio.TimeoutError:
                # Send ping
                await websocket.send_json({"type": "ping", "ts": datetime.utcnow().isoformat()})

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for {user_id}: {e}")
        manager.disconnect(websocket, user_id)


@router.get("/ws/stats")
async def ws_stats():
    """WebSocket connection statistics."""
    return {
        "active_users":       manager.active_users,
        "active_connections": manager.active_connections,
    }
