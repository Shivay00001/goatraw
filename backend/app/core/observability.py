"""
GoatRaw — Observability Layer
Structured logging + Sentry error tracking + custom metrics.
Activate by setting SENTRY_DSN in env vars.
"""

import logging
import os
import time
import json
from functools import wraps
from typing import Callable, Any

# ── Sentry (optional) ─────────────────────────────────────────
SENTRY_DSN = os.getenv("SENTRY_DSN", "")

if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        sentry_sdk.init(
            dsn         = SENTRY_DSN,
            environment = os.getenv("ENVIRONMENT", "production"),
            traces_sample_rate = 0.1,   # 10% of requests traced
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
            ],
        )
        print("✓ Sentry initialized")
    except ImportError:
        print("⚠ sentry-sdk not installed. Run: pip install sentry-sdk[fastapi]")


# ── Structured JSON logger ────────────────────────────────────

class StructuredLogger(logging.Logger):
    """Logger that outputs JSON lines for log aggregation (Datadog, Loki, etc.)."""

    def _log_json(self, level: str, msg: str, extra: dict = None):
        record = {
            "ts":      time.time(),
            "level":   level,
            "msg":     msg,
            "service": "goatraw",
            **(extra or {}),
        }
        print(json.dumps(record))

    def info(self,  msg, *args, extra=None, **kwargs): self._log_json("INFO",    str(msg), extra)
    def error(self, msg, *args, extra=None, **kwargs): self._log_json("ERROR",   str(msg), extra)
    def warn(self,  msg, *args, extra=None, **kwargs): self._log_json("WARNING", str(msg), extra)
    def debug(self, msg, *args, extra=None, **kwargs): pass  # Disabled in prod


# ── Metrics (in-memory, export to Redis) ─────────────────────

class MetricsCollector:
    """
    Lightweight in-process metrics.
    In production use Prometheus client + Grafana or Datadog.
    """

    def __init__(self):
        self._counters:   dict[str, int]   = {}
        self._histograms: dict[str, list]  = {}

    def increment(self, metric: str, value: int = 1, tags: dict = None) -> None:
        key = self._make_key(metric, tags)
        self._counters[key] = self._counters.get(key, 0) + value

    def timing(self, metric: str, duration_ms: float, tags: dict = None) -> None:
        key = self._make_key(metric, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(duration_ms)
        # Keep last 1000 samples
        if len(self._histograms[key]) > 1000:
            self._histograms[key] = self._histograms[key][-1000:]

    def get_summary(self) -> dict:
        summary = {"counters": self._counters, "histograms": {}}
        for key, values in self._histograms.items():
            if values:
                sorted_v = sorted(values)
                n        = len(sorted_v)
                summary["histograms"][key] = {
                    "count":  n,
                    "p50":    sorted_v[int(n * 0.50)],
                    "p95":    sorted_v[int(n * 0.95)],
                    "p99":    sorted_v[int(n * 0.99)],
                    "mean":   sum(sorted_v) / n,
                }
        return summary

    def _make_key(self, metric: str, tags: dict = None) -> str:
        if not tags:
            return metric
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{metric}[{tag_str}]"


metrics = MetricsCollector()


# ── Decorator: trace function execution ──────────────────────

def traced(metric_name: str):
    """Decorator to time and count function executions."""
    def decorator(fn: Callable):
        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await fn(*args, **kwargs)
                metrics.increment(f"{metric_name}.success")
                return result
            except Exception as e:
                metrics.increment(f"{metric_name}.error")
                if SENTRY_DSN:
                    import sentry_sdk
                    sentry_sdk.capture_exception(e)
                raise
            finally:
                metrics.timing(f"{metric_name}.duration_ms", (time.time() - start) * 1000)

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = fn(*args, **kwargs)
                metrics.increment(f"{metric_name}.success")
                return result
            except Exception as e:
                metrics.increment(f"{metric_name}.error")
                raise
            finally:
                metrics.timing(f"{metric_name}.duration_ms", (time.time() - start) * 1000)

        return async_wrapper if __import__("asyncio").iscoroutinefunction(fn) else sync_wrapper
    return decorator


# ── Metrics API endpoint ──────────────────────────────────────

from fastapi import APIRouter, Depends
from app.api.deps import get_current_user

obs_router = APIRouter()


@obs_router.get("/metrics")
async def get_metrics(user=Depends(get_current_user)):
    """Internal metrics endpoint (authenticated)."""
    if user.get("plan") not in ("enterprise",) and user.get("email") not in os.getenv("ADMIN_EMAILS", "").split(","):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Metrics require enterprise plan.")
    return metrics.get_summary()


# ── Alert thresholds ──────────────────────────────────────────

async def check_alerts() -> list[dict]:
    """Check system health and return any alerts."""
    alerts = []
    from app.core.redis_client import get_redis
    r = get_redis()

    # Queue depth alert
    depth = await r.llen("goatraw:task_queue")
    if depth > 100:
        alerts.append({"type": "queue_depth", "value": depth, "threshold": 100, "severity": "warning"})
    if depth > 500:
        alerts.append({"type": "queue_depth", "value": depth, "threshold": 500, "severity": "critical"})

    # Error rate from metrics
    summary = metrics.get_summary()
    for key, count in summary.get("counters", {}).items():
        if ".error" in key and count > 50:
            alerts.append({"type": "error_rate", "metric": key, "count": count, "severity": "warning"})

    return alerts
