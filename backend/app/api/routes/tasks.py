"""
GoatRaw - Task API Routes
POST /task/create  — create and enqueue a task
GET  /task/{id}    — get task status + result
GET  /task/        — list user's tasks
DELETE /task/{id}  — cancel a task
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Any
import uuid

from app.core.redis_client import (
    enqueue_task, get_task_status, get_task_result, set_task_status
)
from app.api.deps import get_current_user, check_rate_limit_for_user
from app.core.database import get_db
from app.models.task import Task, TaskStatus, TaskType
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TaskCreateRequest(BaseModel):
    goal: str = Field(..., min_length=10, max_length=2000, description="What should the agent do?")
    agent_type: str = Field("general", description="Agent specialization")
    context: Optional[dict] = Field(default={}, description="Extra context for the agent")
    priority: str = Field("normal", description="normal | high")


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str
    message: str
    estimated_duration_seconds: int


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/create", response_model=TaskCreateResponse, status_code=201)
async def create_task(
    body: TaskCreateRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create and enqueue a new agent task with DB persistence."""
    await check_rate_limit_for_user(user)

    task_id = uuid.uuid4()
    
    # Register in DB
    new_task = Task(
        id=task_id,
        user_id=user["id"],
        goal=body.goal,
        agent_type=body.agent_type,
        status=TaskStatus.QUEUED,
        context=body.context or {},
    )
    db.add(new_task)
    await db.commit()

    # Enqueue in Redis
    await enqueue_task(str(task_id), {
        "goal": body.goal,
        "agent_type": body.agent_type,
        "context": body.context or {},
        "user_id": str(user["id"]),
        "priority": body.priority,
    })

    return TaskCreateResponse(
        task_id=str(task_id),
        status="queued",
        message="Task queued. Poll GET /task/{task_id} for status.",
        estimated_duration_seconds=60,
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task(
    task_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get task status and result (checks Redis first, then DB)."""
    task_status = await get_task_status(task_id)
    
    # If not in Redis, check DB
    if task_status is None:
        stmt = select(Task).where(Task.id == task_id)
        result = await db.execute(stmt)
        db_task = result.scalar_one_or_none()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found.")
        task_status = db_task.status

    result_data = None
    if task_status in ("completed", "failed"):
        result_data = await get_task_result(task_id)
        if not result_data:
            # Check for output table record (implementation skipped here for brevity)
            pass

    return TaskStatusResponse(
        task_id=task_id,
        status=task_status,
        result=result_data,
    )

@router.get("/", response_model=list[TaskStatusResponse])
async def list_tasks(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all tasks for current user from DB."""
    stmt = select(Task).where(Task.user_id == user["id"]).order_by(Task.created_at.desc()).limit(20)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    return [
        TaskStatusResponse(task_id=str(t.id), status=t.status)
        for t in tasks
    ]


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    user=Depends(get_current_user),
):
    """Mark a task as cancelled (best-effort — cannot stop an in-progress worker)."""
    current_status = await get_task_status(task_id)
    if current_status is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    if current_status in ("completed", "failed"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel task in status: {current_status}")

    await set_task_status(task_id, "cancelled")
    return {"task_id": task_id, "status": "cancelled"}
