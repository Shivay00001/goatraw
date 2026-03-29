"""
GoatRaw — Webhook Security
Signature verification for every inbound channel webhook.
Prevents spoofed requests from triggering agent tasks.
"""

import hmac
import hashlib
import logging
import os
import time
from typing import Optional

logger = logging.getLogger("goatraw.webhook_security")


# ── Telegram ──────────────────────────────────────────────────

def verify_telegram_update(body_bytes: bytes, secret_token: str, header_token: str) -> bool:
    """
    Telegram Bot API sends X-Telegram-Bot-Api-Secret-Token header.
    Set it when registering webhook: setWebhook?secret_token=YOUR_TOKEN
    """
    if not secret_token:
        return True   # No secret configured → allow (set one in prod!)
    return hmac.compare_digest(header_token or "", secret_token)


# ── Slack ─────────────────────────────────────────────────────

def verify_slack_signature(
    body_bytes:      bytes,
    timestamp_header: str,
    signature_header: str,
    signing_secret:   str,
) -> bool:
    """
    Slack signing secret verification (v0).
    https://api.slack.com/authentication/verifying-requests-from-slack
    """
    if not signing_secret:
        return True

    # Replay attack protection: reject requests > 5 minutes old
    try:
        ts = int(timestamp_header or "0")
        if abs(time.time() - ts) > 300:
            logger.warning("Slack webhook: timestamp too old (possible replay attack)")
            return False
    except (ValueError, TypeError):
        return False

    base_string = f"v0:{timestamp_header}:{body_bytes.decode()}"
    computed    = "v0=" + hmac.new(
        signing_secret.encode(),
        base_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, signature_header or "")


# ── WhatsApp (Meta) ───────────────────────────────────────────

def verify_meta_signature(body_bytes: bytes, signature_header: str, app_secret: str) -> bool:
    """
    Meta (WhatsApp/Facebook) webhook signature verification.
    Header: X-Hub-Signature-256: sha256=<hash>
    """
    if not app_secret:
        return True

    expected = "sha256=" + hmac.new(
        app_secret.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header or "")


# ── Discord ───────────────────────────────────────────────────

def verify_discord_signature(
    body_bytes:      bytes,
    timestamp_header: str,
    signature_header: str,
    public_key:       str,
) -> bool:
    """
    Discord interaction endpoint verification using Ed25519.
    Requires `cryptography` package.
    """
    if not public_key:
        return True

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        import binascii

        key       = Ed25519PublicKey.from_public_bytes(binascii.unhexlify(public_key))
        message   = (timestamp_header or "").encode() + body_bytes
        key.verify(binascii.unhexlify(signature_header or ""), message)
        return True
    except Exception:
        return False


# ── Generic HMAC (webhook.site, custom) ──────────────────────

def verify_hmac_sha256(body_bytes: bytes, signature: str, secret: str, prefix: str = "sha256=") -> bool:
    """Generic HMAC-SHA256 signature verification."""
    if not secret:
        return True
    expected = prefix + hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


# ── FastAPI dependency helpers ────────────────────────────────

from fastapi import Request, HTTPException


async def require_telegram_auth(request: Request) -> None:
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    token  = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret and not verify_telegram_update(b"", secret, token):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook token")


async def require_slack_auth(request: Request) -> None:
    secret    = os.getenv("SLACK_SIGNING_SECRET", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    body      = await request.body()
    if secret and not verify_slack_signature(body, timestamp, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


async def require_meta_auth(request: Request) -> None:
    secret    = os.getenv("META_APP_SECRET", "")
    signature = request.headers.get("X-Hub-Signature-256", "")
    body      = await request.body()
    if secret and not verify_meta_signature(body, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid Meta webhook signature")
