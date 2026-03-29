"""
GoatRaw - Multi-Channel Gateway
OpenClaw supports WhatsApp, Telegram, Slack, Discord, Signal, iMessage, etc.
GoatRaw implements this as a unified inbound webhook gateway for SaaS.

Each workspace can configure multiple channels.
All inbound messages route through the same agent pipeline.
Outbound notifications go back via the same channel.
"""

import json
import logging
import hashlib
import hmac
from datetime import datetime
from typing import Optional, Dict, Any
import httpx

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel

from app.core.config import settings
from app.core.redis_client import enqueue_task, get_redis
from app.agents.memory_system import GoatRawMemory

logger = logging.getLogger("goatraw.gateway")

router = APIRouter()


# ─── Channel Message Schema ───────────────────────────────────────────────────

class ChannelMessage:
    def __init__(
        self,
        channel: str,
        user_id: str,
        workspace_id: str,
        text: str,
        sender_id: str,
        sender_name: str = "",
        message_id: str = "",
        metadata: dict = None,
    ):
        self.channel = channel
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.text = text
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.message_id = message_id
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow().isoformat()


# ─── Channel Adapters ─────────────────────────────────────────────────────────

class TelegramAdapter:
    """Parse Telegram webhook updates."""

    @staticmethod
    def parse(body: dict, workspace_id: str) -> Optional[ChannelMessage]:
        try:
            message = body.get("message") or body.get("channel_post")
            if not message:
                return None
            chat = message.get("chat", {})
            sender = message.get("from", {})
            text = message.get("text", "")
            if not text:
                return None
            return ChannelMessage(
                channel="telegram",
                user_id=workspace_id,
                workspace_id=workspace_id,
                text=text,
                sender_id=str(sender.get("id", "")),
                sender_name=f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip(),
                message_id=str(message.get("message_id", "")),
                metadata={"chat_id": str(chat.get("id", "")), "chat_type": chat.get("type", "")},
            )
        except Exception as e:
            logger.error(f"Telegram parse error: {e}")
            return None

    @staticmethod
    async def send(chat_id: str, text: str, bot_token: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False


class SlackAdapter:
    """Parse Slack Events API payloads."""

    @staticmethod
    def parse(body: dict, workspace_id: str) -> Optional[ChannelMessage]:
        try:
            event = body.get("event", {})
            if event.get("type") not in ("message", "app_mention"):
                return None
            text = event.get("text", "").strip()
            # Strip bot mention
            if text.startswith("<@"):
                text = text.split(">", 1)[-1].strip()
            if not text:
                return None
            return ChannelMessage(
                channel="slack",
                user_id=workspace_id,
                workspace_id=workspace_id,
                text=text,
                sender_id=event.get("user", ""),
                message_id=event.get("ts", ""),
                metadata={
                    "channel_id": event.get("channel", ""),
                    "thread_ts": event.get("thread_ts"),
                },
            )
        except Exception as e:
            logger.error(f"Slack parse error: {e}")
            return None

    @staticmethod
    async def send(channel_id: str, text: str, bot_token: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    json={"channel": channel_id, "text": text},
                )
                data = resp.json()
                return data.get("ok", False)
        except Exception as e:
            logger.error(f"Slack send failed: {e}")
            return False


class WhatsAppAdapter:
    """Parse WhatsApp Business Cloud API webhooks."""

    @staticmethod
    def parse(body: dict, workspace_id: str) -> Optional[ChannelMessage]:
        try:
            entry = body.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None
            msg = messages[0]
            if msg.get("type") != "text":
                return None
            contacts = value.get("contacts", [{}])
            sender_name = contacts[0].get("profile", {}).get("name", "") if contacts else ""
            return ChannelMessage(
                channel="whatsapp",
                user_id=workspace_id,
                workspace_id=workspace_id,
                text=msg.get("text", {}).get("body", ""),
                sender_id=msg.get("from", ""),
                sender_name=sender_name,
                message_id=msg.get("id", ""),
                metadata={"phone_number_id": value.get("metadata", {}).get("phone_number_id", "")},
            )
        except Exception as e:
            logger.error(f"WhatsApp parse error: {e}")
            return None

    @staticmethod
    async def send(to: str, text: str, phone_number_id: str, access_token: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"https://graph.facebook.com/v18.0/{phone_number_id}/messages",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": to,
                        "type": "text",
                        "text": {"body": text},
                    },
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            return False


class DiscordAdapter:
    """Parse Discord interaction webhooks."""

    @staticmethod
    def parse(body: dict, workspace_id: str) -> Optional[ChannelMessage]:
        try:
            content = body.get("content", "").strip()
            author = body.get("author", {})
            if not content or author.get("bot"):
                return None
            return ChannelMessage(
                channel="discord",
                user_id=workspace_id,
                workspace_id=workspace_id,
                text=content,
                sender_id=author.get("id", ""),
                sender_name=author.get("username", ""),
                message_id=body.get("id", ""),
                metadata={"channel_id": body.get("channel_id", ""), "guild_id": body.get("guild_id", "")},
            )
        except Exception as e:
            logger.error(f"Discord parse error: {e}")
            return None


# ─── Channel Registry ──────────────────────────────────────────────────────────

CHANNEL_PARSERS = {
    "telegram": TelegramAdapter.parse,
    "slack": SlackAdapter.parse,
    "whatsapp": WhatsAppAdapter.parse,
    "discord": DiscordAdapter.parse,
}


# ─── Unified Inbound Router ───────────────────────────────────────────────────

async def route_channel_message(msg: ChannelMessage) -> dict:
    """
    Route an inbound channel message through the agent pipeline.
    Checks for slash commands first, then runs as agent task.
    """
    text = msg.text.strip()

    # ── Built-in Commands (like OpenClaw's /status, /help) ────────────────────
    if text.startswith("/"):
        return await handle_slash_command(msg)

    # ── Regular message → queue as agent task ─────────────────────────────────
    import uuid as uuid_module
    task_id = str(uuid_module.uuid4())

    await enqueue_task(task_id, {
        "goal": text,
        "agent_type": "general",
        "context": {
            "channel": msg.channel,
            "sender_id": msg.sender_id,
            "sender_name": msg.sender_name,
            "reply_metadata": msg.metadata,
        },
        "user_id": msg.workspace_id,
        "source_channel": msg.channel,
        "reply_to": msg.metadata,
    })

    return {"task_id": task_id, "status": "queued"}


async def handle_slash_command(msg: ChannelMessage) -> dict:
    """Handle built-in slash commands from channel messages."""
    parts = msg.text.strip().split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    r = get_redis()

    if cmd == "/status":
        # Get recent task statuses
        recent_key = f"goatraw:user_tasks:{msg.workspace_id}"
        recent = await r.lrange(recent_key, 0, 4)
        task_list = [json.loads(t) for t in recent]
        tasks_text = "\n".join(
            f"• {t.get('task_id', '')[:8]}: {t.get('status', 'unknown')}" for t in task_list
        ) or "No recent tasks"
        return {"response": f"📊 <b>Status</b>\n{tasks_text}", "type": "command"}

    elif cmd == "/memory":
        memory = GoatRawMemory(user_id=msg.workspace_id, session_id="cmd")
        ctx = await memory.build_context()
        return {"response": f"🧠 <b>Memory</b>\n{ctx[:500]}", "type": "command"}

    elif cmd == "/help":
        help_text = """🦞 <b>GoatRaw Commands</b>

/status — Recent task statuses
/memory — Show memory context
/skills — List available skills
/run [goal] — Queue an agent task
/help — Show this message"""
        return {"response": help_text, "type": "command"}

    elif cmd == "/skills":
        from app.agents.skill_system import skill_registry
        skills = await skill_registry.list_skills(msg.workspace_id)
        skills_text = "\n".join(f"• <b>{s['name']}</b>: {s['description'][:60]}" for s in skills[:8])
        return {"response": f"🧩 <b>Available Skills</b>\n{skills_text}", "type": "command"}

    elif cmd == "/run":
        if not args:
            return {"response": "Usage: /run [goal description]", "type": "error"}
        msg.text = args
        return await route_channel_message(msg)

    return {"response": f"Unknown command: {cmd}. Try /help", "type": "error"}


# ─── Webhook Route Handlers ───────────────────────────────────────────────────

@router.post("/webhook/telegram/{workspace_id}")
async def telegram_webhook(workspace_id: str, request: Request):
    body = await request.json()
    msg = TelegramAdapter.parse(body, workspace_id)
    if not msg:
        return {"ok": True}
    result = await route_channel_message(msg)
    return {"ok": True, **result}


@router.post("/webhook/slack/{workspace_id}")
async def slack_webhook(workspace_id: str, request: Request):
    body = await request.json()
    # Slack URL verification
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}
    msg = SlackAdapter.parse(body, workspace_id)
    if not msg:
        return {"ok": True}
    result = await route_channel_message(msg)
    return {"ok": True, **result}


@router.post("/webhook/whatsapp/{workspace_id}")
async def whatsapp_webhook(workspace_id: str, request: Request):
    body = await request.json()
    msg = WhatsAppAdapter.parse(body, workspace_id)
    if not msg:
        return {"ok": True}
    result = await route_channel_message(msg)
    return {"ok": True, **result}


@router.get("/webhook/whatsapp/{workspace_id}")
async def whatsapp_verify(workspace_id: str, request: Request):
    """WhatsApp webhook verification."""
    params = dict(request.query_params)
    verify_token = params.get("hub.verify_token", "")
    if verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return int(params.get("hub.challenge", "0"))
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/discord/{workspace_id}")
async def discord_webhook(workspace_id: str, request: Request):
    body = await request.json()
    msg = DiscordAdapter.parse(body, workspace_id)
    if not msg:
        return {"ok": True}
    result = await route_channel_message(msg)
    return {"ok": True, **result}
