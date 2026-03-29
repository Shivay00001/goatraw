"""
GoatRaw — Outbound Notification Service
Sends task results and alerts back through configured channels.
Used by: heartbeat daemon, scheduler, agent completion hooks.
"""

import httpx
import logging
import json
import os
from typing import Optional, Literal

logger = logging.getLogger("goatraw.notifications")

NotifyChannel = Literal["telegram", "whatsapp", "slack", "webhook", "email"]


# ─── Formatters ───────────────────────────────────────────────

def format_task_result(result: dict, max_data_items: int = 5) -> str:
    """Format a task result dict into a readable notification message."""
    output  = result.get("output", {}) or {}
    status  = output.get("status", result.get("status", "unknown"))
    summary = output.get("summary", "Task completed.")
    data    = output.get("data", {})
    stats   = output.get("stats", {})

    icon = "✅" if status == "success" else ("⚠️" if status == "partial" else "❌")
    msg  = f"{icon} <b>GoatRaw Agent Done</b>\n\n"
    msg += f"{summary}\n"

    if isinstance(data, list) and data:
        msg += f"\n<b>Results ({min(len(data), max_data_items)} of {len(data)}):</b>\n"
        for item in data[:max_data_items]:
            if isinstance(item, dict):
                name  = item.get("company") or item.get("name") or item.get("title") or ""
                email = item.get("email") or ""
                if name or email:
                    msg += f"• {name}{' — ' + email if email else ''}\n"
    elif isinstance(data, dict) and data:
        for k, v in list(data.items())[:5]:
            msg += f"\n<b>{k}:</b> {str(v)[:100]}"

    if stats:
        msg += f"\n\n<i>Steps: {result.get('steps_taken', '?')} | "
        for k, v in list(stats.items())[:2]:
            msg += f"{k}: {v} | "
        msg = msg.rstrip(" | ") + "</i>"

    return msg


# ─── Telegram ─────────────────────────────────────────────────

async def send_telegram(chat_id: str, message: str, bot_token: Optional[str] = None) -> bool:
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id":    chat_id,
                    "text":       message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            ok = resp.json().get("ok", False)
            if not ok:
                logger.warning(f"Telegram send failed: {resp.text[:200]}")
            return ok
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


# ─── WhatsApp ─────────────────────────────────────────────────

async def send_whatsapp(to: str, message: str) -> bool:
    access_token     = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    phone_number_id  = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    if not access_token or not phone_number_id:
        return False
    # WhatsApp doesn't support HTML — strip tags
    import re
    clean = re.sub(r"<[^>]+>", "", message)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://graph.facebook.com/v18.0/{phone_number_id}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to":   to,
                    "type": "text",
                    "text": {"body": clean[:4096]},
                },
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
        return False


# ─── Slack ────────────────────────────────────────────────────

async def send_slack(channel_id: str, message: str, bot_token: Optional[str] = None) -> bool:
    token = bot_token or os.getenv("SLACK_BOT_TOKEN", "")
    if not token or not channel_id:
        return False
    import re
    # Convert HTML tags to Slack mrkdwn
    text = re.sub(r"<b>(.*?)</b>",  r"*\1*",  message)
    text = re.sub(r"<i>(.*?)</i>",  r"_\1_",  text)
    text = re.sub(r"<[^>]+>",       "",        text)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                json={"channel": channel_id, "text": text},
            )
            data = resp.json()
            return data.get("ok", False)
    except Exception as e:
        logger.error(f"Slack error: {e}")
        return False


# ─── Webhook ──────────────────────────────────────────────────

async def send_webhook(url: str, payload: dict) -> bool:
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "User-Agent": "GoatRaw/2.0"},
            )
            return 200 <= resp.status_code < 300
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return False


# ─── Unified Dispatcher ───────────────────────────────────────

async def notify(
    channel:  NotifyChannel,
    endpoint: str,
    message:  str,
    payload:  Optional[dict] = None,
) -> bool:
    """
    Unified notification dispatcher.
    channel:  "telegram" | "whatsapp" | "slack" | "webhook"
    endpoint: chat_id / phone / channel_id / URL
    """
    if channel == "telegram":
        return await send_telegram(endpoint, message)
    elif channel == "whatsapp":
        return await send_whatsapp(endpoint, message)
    elif channel == "slack":
        return await send_slack(endpoint, message)
    elif channel == "webhook":
        return await send_webhook(endpoint, payload or {"message": message})
    else:
        logger.warning(f"Unknown notification channel: {channel}")
        return False


async def notify_task_complete(
    channel:    NotifyChannel,
    endpoint:   str,
    task_result: dict,
) -> bool:
    """High-level helper: format + notify when a task finishes."""
    message = format_task_result(task_result)
    webhook_payload = {
        "type":    "task_complete",
        "task_id": task_result.get("task_id"),
        "status":  task_result.get("status"),
        "output":  task_result.get("output"),
    }
    return await notify(channel, endpoint, message, webhook_payload)
