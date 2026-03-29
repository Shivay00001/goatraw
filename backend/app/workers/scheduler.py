"""
GoatRaw - Scheduled Workflows (Cron System)
OpenClaw: "Recurring actions — repeating tasks on any schedule"
GoatRaw: Per-user cron jobs stored in Redis sorted set, executed by scheduler worker.

Examples:
- "Check competitor pricing every Monday"
- "Find new leads in SaaS niche every day"
- "Send daily market briefing at 8am"
- "Monitor keyword trends every 6 hours"
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass, field

from app.core.redis_client import get_redis, enqueue_task

logger = logging.getLogger("goatraw.scheduler")


# ─── Cron Job Definition ──────────────────────────────────────────────────────

@dataclass
class CronJob:
    id: str
    user_id: str
    name: str
    goal: str                       # The agent task to run
    agent_type: str = "general"
    context: dict = field(default_factory=dict)
    schedule_type: str = "interval" # "interval" | "daily" | "weekly"
    interval_hours: int = 24
    daily_time: str = "08:00"       # HH:MM UTC
    weekly_day: int = 0             # 0=Monday ... 6=Sunday
    enabled: bool = True
    last_run: Optional[str] = None
    run_count: int = 0
    notify_on_complete: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: dict) -> "CronJob":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def next_run_timestamp(self) -> float:
        now = datetime.utcnow()
        if self.schedule_type == "interval":
            return (now + timedelta(hours=self.interval_hours)).timestamp()
        elif self.schedule_type == "daily":
            h, m = map(int, self.daily_time.split(":"))
            next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run.timestamp()
        elif self.schedule_type == "weekly":
            days_ahead = self.weekly_day - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now + timedelta(days=days_ahead)
            h, m = map(int, self.daily_time.split(":"))
            next_run = next_run.replace(hour=h, minute=m, second=0, microsecond=0)
            return next_run.timestamp()
        return (now + timedelta(hours=24)).timestamp()


# ─── Cron Store ───────────────────────────────────────────────────────────────

class CronStore:
    JOBS_PREFIX = "goatraw:cron:job:"
    QUEUE_KEY = "goatraw:cron:queue"
    USER_JOBS_PREFIX = "goatraw:cron:user:"

    async def create(self, job: CronJob) -> str:
        r = get_redis()
        await r.set(f"{self.JOBS_PREFIX}{job.id}", json.dumps(job.to_dict()))
        await r.sadd(f"{self.USER_JOBS_PREFIX}{job.user_id}", job.id)
        # Schedule first run
        next_ts = job.next_run_timestamp()
        await r.zadd(self.QUEUE_KEY, {job.id: next_ts})
        logger.info(f"Cron job {job.id} created: '{job.name}' for user {job.user_id}")
        return job.id

    async def get(self, job_id: str) -> Optional[CronJob]:
        r = get_redis()
        raw = await r.get(f"{self.JOBS_PREFIX}{job_id}")
        return CronJob.from_dict(json.loads(raw)) if raw else None

    async def list_for_user(self, user_id: str) -> List[CronJob]:
        r = get_redis()
        job_ids = await r.smembers(f"{self.USER_JOBS_PREFIX}{user_id}")
        jobs = []
        for jid in job_ids:
            job = await self.get(jid)
            if job:
                jobs.append(job)
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    async def update(self, job: CronJob) -> None:
        r = get_redis()
        await r.set(f"{self.JOBS_PREFIX}{job.id}", json.dumps(job.to_dict()))

    async def delete(self, job_id: str, user_id: str) -> None:
        r = get_redis()
        await r.delete(f"{self.JOBS_PREFIX}{job_id}")
        await r.srem(f"{self.USER_JOBS_PREFIX}{user_id}", job_id)
        await r.zrem(self.QUEUE_KEY, job_id)

    async def get_due_jobs(self) -> List[str]:
        r = get_redis()
        now_ts = datetime.utcnow().timestamp()
        return await r.zrangebyscore(self.QUEUE_KEY, 0, now_ts)

    async def reschedule(self, job_id: str, next_ts: float) -> None:
        r = get_redis()
        await r.zadd(self.QUEUE_KEY, {job_id: next_ts})


cron_store = CronStore()


# ─── Scheduler Worker ─────────────────────────────────────────────────────────

async def scheduler_loop():
    """
    Scheduler daemon — runs alongside heartbeat daemon.
    Checks for due cron jobs every 30 seconds.
    """
    from app.core.redis_client import init_redis
    await init_redis()
    logger.info("GoatRaw Scheduler started.")

    while True:
        try:
            due_job_ids = await cron_store.get_due_jobs()
            for job_id in due_job_ids:
                job = await cron_store.get(job_id)
                if not job or not job.enabled:
                    continue
                asyncio.create_task(execute_cron_job(job))

            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(60)


async def execute_cron_job(job: CronJob) -> None:
    """Execute a single cron job."""
    logger.info(f"Executing cron job '{job.name}' for user {job.user_id}")
    task_id = str(uuid.uuid4())

    try:
        await enqueue_task(task_id, {
            "goal": job.goal,
            "agent_type": job.agent_type,
            "context": {**job.context, "cron_job_id": job.id, "cron_job_name": job.name},
            "user_id": job.user_id,
            "is_scheduled": True,
        })

        job.last_run = datetime.utcnow().isoformat()
        job.run_count += 1
        await cron_store.update(job)

        # Reschedule
        next_ts = job.next_run_timestamp()
        await cron_store.reschedule(job.id, next_ts)

        logger.info(f"Cron job '{job.name}' dispatched as task {task_id}")

    except Exception as e:
        logger.error(f"Cron job execution failed: {e}")
        # Reschedule even on failure
        await cron_store.reschedule(job.id, job.next_run_timestamp())


# ─── Cron API Routes ──────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.api.deps import get_current_user

cron_router = APIRouter()


class CreateCronRequest(BaseModel):
    name: str = Field(..., min_length=3)
    goal: str = Field(..., min_length=10)
    agent_type: str = "general"
    context: dict = {}
    schedule_type: str = "interval"
    interval_hours: int = 24
    daily_time: str = "08:00"
    weekly_day: int = 0
    notify_on_complete: bool = True


@cron_router.post("/cron/create")
async def create_cron_job(body: CreateCronRequest, user=Depends(get_current_user)):
    job = CronJob(
        id=str(uuid.uuid4())[:12],
        user_id=str(user["id"]),
        **body.dict(),
    )
    job_id = await cron_store.create(job)
    return {"job_id": job_id, "name": job.name, "status": "scheduled", "next_run": datetime.fromtimestamp(job.next_run_timestamp()).isoformat()}


@cron_router.get("/cron/list")
async def list_cron_jobs(user=Depends(get_current_user)):
    jobs = await cron_store.list_for_user(str(user["id"]))
    return {"jobs": [j.to_dict() for j in jobs]}


@cron_router.delete("/cron/{job_id}")
async def delete_cron_job(job_id: str, user=Depends(get_current_user)):
    await cron_store.delete(job_id, str(user["id"]))
    return {"job_id": job_id, "status": "deleted"}
