"""
GoatRaw - Redis Client
Used for: task queue, caching, rate limiting, pub/sub for task status.
"""

import redis.asyncio as aioredis
import json
import logging
from typing import Any, Optional
from app.core.config import settings

logger = logging.getLogger("goatraw.redis")

redis_client: Optional[aioredis.Redis] = None


async def init_redis():
    global redis_client
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    await redis_client.ping()
    logger.info("Redis connected.")


def get_redis() -> aioredis.Redis:
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client


# ─── Task Queue Operations ────────────────────────────────────────────────────

TASK_QUEUE_KEY = "goatraw:task_queue"
TASK_STATUS_PREFIX = "goatraw:task_status:"
TASK_RESULT_PREFIX = "goatraw:task_result:"


async def enqueue_task(task_id: str, payload: dict) -> None:
    r = get_redis()
    await r.lpush(TASK_QUEUE_KEY, json.dumps({"task_id": task_id, **payload}))
    await r.set(f"{TASK_STATUS_PREFIX}{task_id}", "queued", ex=86400)
    logger.info(f"Task {task_id} enqueued.")


async def dequeue_task(timeout: int = 10) -> Optional[dict]:
    r = get_redis()
    result = await r.brpop(TASK_QUEUE_KEY, timeout=timeout)
    if result:
        _, raw = result
        return json.loads(raw)
    return None


async def set_task_status(task_id: str, status: str) -> None:
    r = get_redis()
    await r.set(f"{TASK_STATUS_PREFIX}{task_id}", status, ex=86400)


async def get_task_status(task_id: str) -> Optional[str]:
    r = get_redis()
    return await r.get(f"{TASK_STATUS_PREFIX}{task_id}")


async def set_task_result(task_id: str, result: Any) -> None:
    r = get_redis()
    await r.set(f"{TASK_RESULT_PREFIX}{task_id}", json.dumps(result), ex=3600)


async def get_task_result(task_id: str) -> Optional[Any]:
    r = get_redis()
    raw = await r.get(f"{TASK_RESULT_PREFIX}{task_id}")
    return json.loads(raw) if raw else None


# ─── Rate Limiting ────────────────────────────────────────────────────────────

async def check_rate_limit(user_id: str, limit: int) -> bool:
    """
    Sliding window rate limiter.
    Returns True if request is allowed, False if rate limited.
    """
    r = get_redis()
    key = f"goatraw:ratelimit:{user_id}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 3600)
    results = await pipe.execute()
    count = results[0]
    return count <= limit
