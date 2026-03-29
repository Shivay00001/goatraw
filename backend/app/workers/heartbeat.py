"""
GoatRaw - Heartbeat Daemon
OpenClaw's most distinctive feature: the agent wakes up on a schedule,
checks a to-do list (HEARTBEAT checklist), and acts autonomously.

In GoatRaw (SaaS): each user has a heartbeat config stored in DB/Redis.
The daemon runs as a background worker, processes each user's heartbeat on schedule.
Proactively sends updates via configured channels (WhatsApp, Telegram, Email, Webhook).
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.redis_client import get_redis
from app.services.llm_adapter import generate, ModelType
from app.agents.memory_system import GoatRawMemory

logger = logging.getLogger("goatraw.heartbeat")


# ─── Heartbeat Config ─────────────────────────────────────────────────────────

@dataclass
class HeartbeatConfig:
    user_id: str
    enabled: bool = True
    interval_minutes: int = 30          # Default: every 30 min (like OpenClaw)
    checklist: List[str] = field(default_factory=list)   # Things to check each beat
    notify_channel: str = "webhook"     # "webhook" | "telegram" | "whatsapp" | "email"
    notify_endpoint: str = ""           # Webhook URL or channel ID
    silent_ok: bool = True              # OpenClaw model: only notify if action needed
    last_run: Optional[str] = None
    next_run: Optional[str] = None

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: dict) -> "HeartbeatConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── Heartbeat Store ──────────────────────────────────────────────────────────

class HeartbeatStore:
    """Manages heartbeat configs in Redis."""

    PREFIX = "goatraw:heartbeat:config:"
    QUEUE_KEY = "goatraw:heartbeat:due"

    async def save(self, config: HeartbeatConfig) -> None:
        r = get_redis()
        await r.set(f"{self.PREFIX}{config.user_id}", json.dumps(config.to_dict()))
        # Schedule next run in sorted set (score = unix timestamp)
        if config.enabled:
            next_ts = (datetime.utcnow() + timedelta(minutes=config.interval_minutes)).timestamp()
            await r.zadd(self.QUEUE_KEY, {config.user_id: next_ts})

    async def get(self, user_id: str) -> Optional[HeartbeatConfig]:
        r = get_redis()
        raw = await r.get(f"{self.PREFIX}{user_id}")
        return HeartbeatConfig.from_dict(json.loads(raw)) if raw else None

    async def get_due_users(self) -> List[str]:
        """Get all users whose heartbeat is due right now."""
        r = get_redis()
        now_ts = datetime.utcnow().timestamp()
        user_ids = await r.zrangebyscore(self.QUEUE_KEY, 0, now_ts)
        return user_ids

    async def mark_completed(self, user_id: str, interval_minutes: int) -> None:
        r = get_redis()
        next_ts = (datetime.utcnow() + timedelta(minutes=interval_minutes)).timestamp()
        await r.zadd(self.QUEUE_KEY, {user_id: next_ts})


heartbeat_store = HeartbeatStore()


# ─── Heartbeat Executor ───────────────────────────────────────────────────────

HEARTBEAT_SYSTEM_PROMPT = """You are GoatRaw's proactive heartbeat agent.

Your job is to review a checklist and determine if any action is needed.
Rules:
1. If everything is fine — respond with HEARTBEAT_OK (no notification sent)
2. If something needs attention — respond with a concise, actionable notification
3. Never fabricate data. Only report real findings from your checklist
4. Be brief and direct. No fluff.

Respond in JSON:
{
  "status": "OK" | "ACTION_NEEDED",
  "message": "...",
  "actions_taken": [],
  "recommended_actions": []
}"""


async def run_heartbeat_for_user(user_id: str) -> dict:
    """
    Execute one heartbeat cycle for a user.
    Checks their checklist, decides if action needed, optionally notifies.
    """
    config = await heartbeat_store.get(user_id)
    if not config or not config.enabled:
        return {"status": "skipped", "reason": "heartbeat disabled"}

    logger.info(f"Heartbeat firing for user {user_id}")

    # Build memory context
    session_id = f"heartbeat_{datetime.utcnow().strftime('%Y%m%d_%H%M')}"
    memory = GoatRawMemory(user_id=user_id, session_id=session_id)
    memory_context = await memory.build_context(query="ongoing tasks and reminders")

    checklist_text = "\n".join(f"- {item}" for item in config.checklist) if config.checklist else "- Check for any pending tasks\n- Review upcoming deadlines"

    prompt = f"""Current time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

User's heartbeat checklist:
{checklist_text}

Memory context:
{memory_context[:2000]}

Review the checklist. Determine if any items need attention or action."""

    try:
        result = await generate(
            prompt=prompt,
            model_type=ModelType.FAST,
            system_prompt=HEARTBEAT_SYSTEM_PROMPT,
        )

        # Parse result
        try:
            clean = result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            beat_result = json.loads(clean)
        except Exception:
            beat_result = {"status": "OK", "message": result[:500]}

        # Notify if action needed (silent OK model)
        if beat_result.get("status") == "ACTION_NEEDED" or not config.silent_ok:
            await send_heartbeat_notification(user_id, config, beat_result)

        # Update next run
        await heartbeat_store.mark_completed(user_id, config.interval_minutes)

        # Log to session memory
        await memory.log_interaction("agent", f"[HEARTBEAT] {beat_result.get('message', 'OK')}", metadata={"type": "heartbeat"})

        config.last_run = datetime.utcnow().isoformat()
        await heartbeat_store.save(config)

        return beat_result

    except Exception as e:
        logger.error(f"Heartbeat failed for {user_id}: {e}")
        return {"status": "error", "error": str(e)}


async def send_heartbeat_notification(user_id: str, config: HeartbeatConfig, result: dict) -> None:
    """Send notification via configured channel."""
    message = result.get("message", "GoatRaw heartbeat check")

    if config.notify_channel == "webhook" and config.notify_endpoint:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(config.notify_endpoint, json={
                    "user_id": user_id,
                    "type": "heartbeat",
                    "status": result.get("status"),
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat(),
                    "recommended_actions": result.get("recommended_actions", []),
                })
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")

    elif config.notify_channel == "telegram" and config.notify_endpoint:
        await send_telegram_notification(config.notify_endpoint, message)


async def send_telegram_notification(chat_id: str, message: str) -> None:
    """Send Telegram message via Bot API."""
    import httpx, os
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": f"🦞 GoatRaw Heartbeat\n\n{message}", "parse_mode": "HTML"},
            )
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


# ─── Heartbeat Daemon Loop ────────────────────────────────────────────────────

async def heartbeat_daemon_loop():
    """
    Background daemon that continuously checks for due heartbeats.
    Runs as a separate process alongside the main worker.
    """
    logger.info("GoatRaw Heartbeat Daemon started.")
    from app.core.redis_client import init_redis
    await init_redis()

    while True:
        try:
            due_users = await heartbeat_store.get_due_users()
            if due_users:
                logger.info(f"Processing {len(due_users)} heartbeats...")
                tasks = [run_heartbeat_for_user(uid) for uid in due_users]
                await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Heartbeat daemon error: {e}")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(heartbeat_daemon_loop())
