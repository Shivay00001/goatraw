"""
GoatRaw - Background Worker
Runs as a separate process. Pulls tasks from Redis queue and executes agents.

Deploy separately on Render as a Background Worker service.
Command: python -m app.worker
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

from app.core.config import settings
from app.core.redis_client import init_redis, dequeue_task, set_task_status, set_task_result, get_redis
from app.agents.orchestrator import (
    GoatRawAgent,
    create_lead_gen_agent,
    create_market_research_agent,
    create_competitor_analysis_agent,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("goatraw.worker")

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received. Finishing current task...")
    running = False


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


async def process_task(task_payload: dict) -> None:
    """Route a task payload to the correct agent and execute it."""
    task_id = task_payload.get("task_id")
    goal = task_payload.get("goal", "")
    agent_type = task_payload.get("agent_type", "general")
    context = task_payload.get("context", {})

    logger.info(f"Processing task {task_id} | type={agent_type}")

    try:
        # ── Route to specialized agent if applicable ──────────────
        if agent_type == "lead_generation" and context.get("specialized"):
            agent = create_lead_gen_agent(
                task_id=task_id,
                niche=context.get("niche", goal),
                location=context.get("location", ""),
                filters=context.get("filters", {}),
            )
        elif agent_type == "market_research" and context.get("specialized"):
            agent = create_market_research_agent(task_id=task_id, topic=context.get("topic", goal))
        elif agent_type == "competitor_analysis" and context.get("specialized"):
            agent = create_competitor_analysis_agent(
                task_id=task_id,
                company=context.get("company", ""),
                industry=context.get("industry", ""),
            )
        else:
            agent = GoatRawAgent(
                task_id=task_id,
                goal=goal,
                agent_type=agent_type,
                context=context,
            )

        # ── Execute ───────────────────────────────────────────────
        result = await asyncio.wait_for(
            agent.run(),
            timeout=settings.TASK_TIMEOUT_SECONDS,
        )

        logger.info(f"Task {task_id} completed with status: {result.get('status')}")

    except asyncio.TimeoutError:
        logger.error(f"Task {task_id} timed out after {settings.TASK_TIMEOUT_SECONDS}s")
        await set_task_status(task_id, "failed")
        await set_task_result(task_id, {
            "task_id": task_id,
            "status": "failed",
            "error": f"Task timed out after {settings.TASK_TIMEOUT_SECONDS} seconds",
        })
    except Exception as e:
        logger.error(f"Task {task_id} crashed: {e}", exc_info=True)
        await set_task_status(task_id, "failed")
        await set_task_result(task_id, {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
        })


async def worker_loop():
    """Main worker loop — continuously pulls and processes tasks."""
    await init_redis()
    logger.info("GoatRaw Worker started. Waiting for tasks...")

    while running:
        try:
            task = await dequeue_task(timeout=5)
            if task:
                await process_task(task)
            else:
                # No task — loop again
                pass
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(2)

    logger.info("Worker stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(worker_loop())
