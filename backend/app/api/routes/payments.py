"""
GoatRaw — Razorpay Payment Integration
Handles plan upgrades, subscription creation, and webhook verification.
Supports: Free → Pro (₹2,999/mo) and Pro → Enterprise (₹14,999/mo)
"""

import hmac
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.redis_client import get_redis

logger = logging.getLogger("goatraw.payments")

router = APIRouter()

RAZORPAY_KEY_ID     = os.getenv("RAZORPAY_KEY_ID",     "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_BASE       = "https://api.razorpay.com/v1"

# ── Plan configs ──────────────────────────────────────────────
PLANS = {
    "pro": {
        "name":        "GoatRaw Pro",
        "amount":      299900,   # paise (₹2,999)
        "currency":    "INR",
        "period":      "monthly",
        "interval":    1,
        "description": "100 tasks/hr, all channels, heartbeat, 20 cron jobs",
    },
    "enterprise": {
        "name":        "GoatRaw Enterprise",
        "amount":      1499900,  # ₹14,999
        "currency":    "INR",
        "period":      "monthly",
        "interval":    1,
        "description": "1000 tasks/hr, unlimited everything, API access",
    },
}

# ── Razorpay API helpers ──────────────────────────────────────

def _razorpay_auth():
    import base64
    creds = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


async def _rz_post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{RAZORPAY_BASE}{path}", headers=_razorpay_auth(), json=body)
        resp.raise_for_status()
        return resp.json()


async def _rz_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{RAZORPAY_BASE}{path}", headers=_razorpay_auth())
        resp.raise_for_status()
        return resp.json()


# ── Subscription creation ─────────────────────────────────────

async def create_razorpay_plan(plan_key: str) -> str:
    """Create a Razorpay plan if it doesn't exist. Returns plan_id."""
    r = get_redis()
    cache_key = f"goatraw:razorpay:plan_id:{plan_key}"
    cached = await r.get(cache_key)
    if cached:
        return cached

    plan_config = PLANS[plan_key]
    body = {
        "period":   plan_config["period"],
        "interval": plan_config["interval"],
        "item": {
            "name":        plan_config["name"],
            "amount":      plan_config["amount"],
            "currency":    plan_config["currency"],
            "description": plan_config["description"],
        },
    }
    data = await _rz_post("/plans", body)
    plan_id = data["id"]
    await r.set(cache_key, plan_id, ex=86400 * 30)
    return plan_id


async def create_subscription(user_id: str, plan_key: str, email: str, name: str) -> dict:
    """Create a Razorpay subscription for a user."""
    if not RAZORPAY_KEY_ID:
        raise HTTPException(status_code=503, detail="Payment provider not configured.")

    plan_id = await create_razorpay_plan(plan_key)

    subscription = await _rz_post("/subscriptions", {
        "plan_id":        plan_id,
        "total_count":    12,   # 12 monthly payments = 1 year
        "quantity":       1,
        "customer_notify": 1,
        "notes": {
            "goatraw_user_id": user_id,
            "plan":            plan_key,
        },
    })

    # Store subscription in Redis
    r = get_redis()
    await r.set(
        f"goatraw:subscription:{user_id}",
        json.dumps({
            "subscription_id": subscription["id"],
            "plan":            plan_key,
            "status":          "created",
            "created_at":      datetime.utcnow().isoformat(),
        }),
        ex=86400 * 400,
    )

    return {
        "subscription_id":   subscription["id"],
        "plan":              plan_key,
        "razorpay_key_id":   RAZORPAY_KEY_ID,
        "amount":            PLANS[plan_key]["amount"],
        "currency":          "INR",
        "prefill": {"name": name, "email": email},
        "notes": {"plan": plan_key, "user_id": user_id},
    }


# ── Signature verification ────────────────────────────────────

def verify_payment_signature(
    razorpay_payment_id:     str,
    razorpay_subscription_id: str,
    razorpay_signature:       str,
) -> bool:
    """Verify payment signature for subscription payments."""
    body    = f"{razorpay_payment_id}|{razorpay_subscription_id}"
    digest  = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, razorpay_signature)


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify Razorpay webhook signature."""
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return True
    digest = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature or "")


# ── Plan activation ───────────────────────────────────────────

async def activate_plan(user_id: str, plan: str) -> None:
    """Activate a paid plan for a user (update JWT payload in Redis)."""
    r = get_redis()
    key = f"goatraw:user_plan:{user_id}"
    await r.set(key, json.dumps({
        "plan":       plan,
        "activated":  datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(days=31)).isoformat(),
    }), ex=86400 * 32)
    logger.info(f"Plan '{plan}' activated for user {user_id}")


async def get_user_plan(user_id: str) -> str:
    """Get current active plan for a user."""
    r = get_redis()
    raw = await r.get(f"goatraw:user_plan:{user_id}")
    if raw:
        data = json.loads(raw)
        if data.get("expires_at") and datetime.fromisoformat(data["expires_at"]) > datetime.utcnow():
            return data["plan"]
    return "free"


# ── API Routes ────────────────────────────────────────────────

class CreateSubscriptionRequest(BaseModel):
    plan: str   # "pro" | "enterprise"


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id:      str
    razorpay_subscription_id: str
    razorpay_signature:       str
    plan:                     str


@router.post("/subscribe")
async def subscribe(body: CreateSubscriptionRequest, user=Depends(get_current_user)):
    """Create a Razorpay subscription for plan upgrade."""
    if body.plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {body.plan}")

    try:
        data = await create_subscription(
            user_id  = str(user["id"]),
            plan_key = body.plan,
            email    = user.get("email", ""),
            name     = user.get("full_name", "GoatRaw User"),
        )
        return data
    except httpx.HTTPError as e:
        logger.error(f"Razorpay API error: {e}")
        raise HTTPException(status_code=502, detail="Payment provider error. Try again.")


@router.post("/verify-payment")
async def verify_payment(body: VerifyPaymentRequest, user=Depends(get_current_user)):
    """Verify payment signature and activate plan."""
    is_valid = verify_payment_signature(
        body.razorpay_payment_id,
        body.razorpay_subscription_id,
        body.razorpay_signature,
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid payment signature.")

    await activate_plan(str(user["id"]), body.plan)
    logger.info(f"Payment verified: {body.razorpay_payment_id} → {body.plan} for {user['id']}")

    return {
        "status":   "activated",
        "plan":     body.plan,
        "message":  f"Welcome to GoatRaw {body.plan.title()}! Your plan is now active.",
        "features": PLANS[body.plan]["description"],
    }


@router.get("/current-plan")
async def current_plan(user=Depends(get_current_user)):
    """Get current active subscription."""
    plan = await get_user_plan(str(user["id"]))
    r = get_redis()
    raw = await r.get(f"goatraw:subscription:{user['id']}")
    subscription = json.loads(raw) if raw else {}

    return {
        "plan":         plan,
        "subscription": subscription,
        "limits": {
            "free":       {"tasks_per_hour": 10,   "tasks_per_month": 100},
            "pro":        {"tasks_per_hour": 100,  "tasks_per_month": 2000},
            "enterprise": {"tasks_per_hour": 1000, "tasks_per_month": -1},
        }.get(plan, {}),
    }


@router.post("/webhook/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None),
):
    """
    Razorpay webhook endpoint.
    Handles: subscription.activated, subscription.charged, subscription.cancelled
    """
    body = await request.body()

    if not verify_webhook_signature(body, x_razorpay_signature or ""):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = json.loads(body)
    event_type = event.get("event", "")
    payload    = event.get("payload", {})

    logger.info(f"Razorpay webhook: {event_type}")

    if event_type == "subscription.activated":
        sub     = payload.get("subscription", {}).get("entity", {})
        user_id = sub.get("notes", {}).get("goatraw_user_id")
        plan    = sub.get("notes", {}).get("plan")
        if user_id and plan:
            await activate_plan(user_id, plan)

    elif event_type == "subscription.charged":
        sub     = payload.get("subscription", {}).get("entity", {})
        user_id = sub.get("notes", {}).get("goatraw_user_id")
        plan    = sub.get("notes", {}).get("plan")
        if user_id and plan:
            await activate_plan(user_id, plan)  # Renew subscription
            logger.info(f"Subscription renewed: {plan} for {user_id}")

    elif event_type in ("subscription.cancelled", "subscription.completed"):
        sub     = payload.get("subscription", {}).get("entity", {})
        user_id = sub.get("notes", {}).get("goatraw_user_id")
        if user_id:
            r = get_redis()
            await r.delete(f"goatraw:user_plan:{user_id}")
            await r.delete(f"goatraw:subscription:{user_id}")
            logger.info(f"Subscription cancelled for {user_id}")

    return {"status": "ok"}
