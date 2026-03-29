"""
GoatRaw - Cron API Routes
POST /cron/create              — create scheduled workflow
GET  /cron/list                — list all user cron jobs
GET  /cron/{job_id}            — get single job
PATCH /cron/{job_id}           — update job (pause/resume/change schedule)
DELETE /cron/{job_id}          — delete job
POST /cron/{job_id}/run        — run job immediately (one-shot)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime

from app.workers.scheduler import CronJob, cron_store, execute_cron_job
from app.api.deps import get_current_user

router = APIRouter()


class CreateCronRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    goal: str = Field(..., min_length=10, max_length=2000, description="Agent task to run on schedule")
    agent_type: str = Field("auto", description="Agent type or 'auto' for smart routing")
    context: dict = {}
    schedule_type: str = Field("daily", description="interval | daily | weekly")
    interval_hours: int = Field(24, ge=1, le=168)
    daily_time: str = Field("08:00", description="HH:MM UTC for daily/weekly schedules")
    weekly_day: int = Field(0, ge=0, le=6, description="0=Mon...6=Sun for weekly schedule")
    notify_on_complete: bool = True
    skill_id: Optional[str] = None


class UpdateCronRequest(BaseModel):
    enabled: Optional[bool] = None
    name: Optional[str] = None
    schedule_type: Optional[str] = None
    interval_hours: Optional[int] = None
    daily_time: Optional[str] = None
    weekly_day: Optional[int] = None
    notify_on_complete: Optional[bool] = None


@router.post("/create", status_code=201)
async def create_cron_job(body: CreateCronRequest, user=Depends(get_current_user)):
    """Create a new scheduled workflow."""
    job = CronJob(
        id=str(uuid.uuid4())[:12],
        user_id=str(user["id"]),
        name=body.name,
        goal=body.goal,
        agent_type=body.agent_type,
        context={**body.context, **({"skill_id": body.skill_id} if body.skill_id else {})},
        schedule_type=body.schedule_type,
        interval_hours=body.interval_hours,
        daily_time=body.daily_time,
        weekly_day=body.weekly_day,
        notify_on_complete=body.notify_on_complete,
    )
    job_id = await cron_store.create(job)
    next_ts = job.next_run_timestamp()

    return {
        "job_id": job_id,
        "name": job.name,
        "status": "scheduled",
        "schedule_type": job.schedule_type,
        "next_run": datetime.utcfromtimestamp(next_ts).isoformat() + "Z",
    }


@router.get("/list")
async def list_cron_jobs(user=Depends(get_current_user)):
    """List all scheduled workflows for the user."""
    jobs = await cron_store.list_for_user(str(user["id"]))
    return {
        "jobs": [j.to_dict() for j in jobs],
        "total": len(jobs),
        "active": sum(1 for j in jobs if j.enabled),
    }


@router.get("/{job_id}")
async def get_cron_job(job_id: str, user=Depends(get_current_user)):
    """Get details of a single cron job."""
    job = await cron_store.get(job_id)
    if not job or job.user_id != str(user["id"]):
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_dict()


@router.patch("/{job_id}")
async def update_cron_job(job_id: str, body: UpdateCronRequest, user=Depends(get_current_user)):
    """Update schedule or enable/disable a cron job."""
    job = await cron_store.get(job_id)
    if not job or job.user_id != str(user["id"]):
        raise HTTPException(status_code=404, detail="Job not found.")

    update_data = body.dict(exclude_none=True)
    for k, v in update_data.items():
        setattr(job, k, v)

    await cron_store.update(job)
    # Reschedule if timing changed
    if any(k in update_data for k in ("schedule_type", "interval_hours", "daily_time", "weekly_day", "enabled")):
        if job.enabled:
            await cron_store.reschedule(job_id, job.next_run_timestamp())

    return {"job_id": job_id, "status": "updated", **update_data}


@router.delete("/{job_id}")
async def delete_cron_job(job_id: str, user=Depends(get_current_user)):
    """Delete a scheduled workflow."""
    job = await cron_store.get(job_id)
    if not job or job.user_id != str(user["id"]):
        raise HTTPException(status_code=404, detail="Job not found.")
    await cron_store.delete(job_id, str(user["id"]))
    return {"job_id": job_id, "status": "deleted"}


@router.post("/{job_id}/run")
async def run_job_now(job_id: str, user=Depends(get_current_user)):
    """Trigger a cron job to run immediately (one-shot, doesn't affect schedule)."""
    job = await cron_store.get(job_id)
    if not job or job.user_id != str(user["id"]):
        raise HTTPException(status_code=404, detail="Job not found.")
    # Execute in background, return task reference
    import asyncio
    asyncio.create_task(execute_cron_job(job))
    return {"job_id": job_id, "status": "triggered", "message": "Job dispatched. Poll /task/{id} for result."}
