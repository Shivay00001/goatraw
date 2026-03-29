"""GoatRaw — Production Worker v2 (Final)"""
import asyncio, json, logging, signal
from datetime import datetime
import app.agents.tools_extended  # noqa — registers extended tools

from app.core.config import settings
from app.core.redis_client import init_redis, dequeue_task, set_task_status, set_task_result, get_redis
from app.agents.orchestrator_v2 import GoatRawAgentV2, delegator
from app.agents.lead_gen_agent  import LeadGenAgent
from app.workers.heartbeat      import heartbeat_daemon_loop
from app.workers.scheduler      import scheduler_loop
from app.core.database import AsyncSessionLocal
from app.models.task import Task, TaskStatus
from sqlalchemy import update

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger  = logging.getLogger("goatraw.worker_v2")
running = True

def handle_shutdown(signum, frame):
    global running
    logger.info("Shutdown received")
    running = False

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT,  handle_shutdown)


async def process_task(payload: dict) -> None:
    task_id    = payload.get("task_id")
    goal       = payload.get("goal", "")
    agent_type = payload.get("agent_type", "general")
    context    = payload.get("context", {})
    user_id    = payload.get("user_id", "anonymous")
    skill_id   = payload.get("skill_id")

    logger.info(f"[{task_id}] type={agent_type}")
    try:
        if agent_type == "lead_generation" and context.get("specialized"):
            agent = LeadGenAgent(task_id=task_id, niche=context.get("niche", goal),
                                 location=context.get("location",""), filters=context.get("filters",{}))
            result = await asyncio.wait_for(agent.run(), timeout=settings.TASK_TIMEOUT_SECONDS)
        elif agent_type == "auto":
            agent  = await delegator.delegate(goal, user_id, task_id, context)
            result = await asyncio.wait_for(agent.run(), timeout=settings.TASK_TIMEOUT_SECONDS)
        else:
            agent  = GoatRawAgentV2(task_id=task_id, goal=goal, user_id=user_id,
                                    agent_type=agent_type, context=context, skill_id=skill_id)
            result = await asyncio.wait_for(agent.run(), timeout=settings.TASK_TIMEOUT_SECONDS)

        if result:
            await track_usage(user_id, task_id, result.get("steps_taken", 0))
            await update_db_task_status(task_id, TaskStatus.COMPLETED, result.get("steps_taken", 0))
            if context.get("source_channel") and context.get("reply_to"):
                await send_channel_reply(context, result)
    except asyncio.TimeoutError:
        logger.error(f"[{task_id}] TIMEOUT")
        await set_task_status(task_id, "failed")
        await set_task_result(task_id, {"task_id": task_id, "status": "failed", "error": "timeout"})
        await update_db_task_status(task_id, TaskStatus.FAILED)
    except Exception as e:
        logger.error(f"[{task_id}] CRASH: {e}", exc_info=True)
        await set_task_status(task_id, "failed")
        await set_task_result(task_id, {"task_id": task_id, "status": "failed", "error": str(e)})
        await update_db_task_status(task_id, TaskStatus.FAILED)


async def track_usage(user_id: str, task_id: str, steps: int) -> None:
    r   = get_redis()
    key = f"goatraw:usage:{user_id}:{datetime.utcnow().strftime('%Y%m')}"
    await r.hincrby(key, "task_count", 1)
    await r.hincrby(key, "step_count", steps)
    await r.expire(key, 86400 * 45)
    rk = f"goatraw:user_tasks:{user_id}"
    await r.lpush(rk, json.dumps({"task_id": task_id, "status": "completed"}))
    await r.ltrim(rk, 0, 9)
    await r.expire(rk, 86400 * 7)

async def update_db_task_status(task_id: str, status: TaskStatus, steps: int = 0) -> None:
    """Sync task status back to PostgreSQL."""
    try:
        async with AsyncSessionLocal() as db:
            stmt = update(Task).where(Task.id == task_id).values(
                status=status,
                steps_taken=steps,
                completed_at=datetime.utcnow() if status in (TaskStatus.COMPLETED, TaskStatus.FAILED) else None
            )
            await db.execute(stmt)
            await db.commit()
    except Exception as e:
        logger.error(f"DB Status sync failed for {task_id}: {e}")


async def send_channel_reply(context: dict, result: dict) -> None:
    import os
    from app.services.notification_service import format_task_result
    channel  = context.get("source_channel")
    reply_to = context.get("reply_to", {})
    message  = format_task_result(result)
    if channel == "telegram":
        from app.api.routes.channels import TelegramAdapter
        chat_id = reply_to.get("chat_id","")
        token   = os.getenv("TELEGRAM_BOT_TOKEN","")
        if chat_id and token:
            await TelegramAdapter.send(chat_id, message[:4096], token)
    elif channel == "slack":
        from app.api.routes.channels import SlackAdapter
        ch_id = reply_to.get("channel_id","")
        token = os.getenv("SLACK_BOT_TOKEN","")
        if ch_id and token:
            await SlackAdapter.send(ch_id, message, token)


async def worker_main():
    await init_redis()
    logger.info("GoatRaw Worker v2 started ✓")
    asyncio.create_task(heartbeat_daemon_loop())
    asyncio.create_task(scheduler_loop())
    while running:
        try:
            task = await dequeue_task(timeout=5)
            if task:
                asyncio.create_task(process_task(task))
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(2)
    logger.info("Worker v2 stopped.")

if __name__ == "__main__":
    asyncio.run(worker_main())
