"""
GoatRaw — Rate Limiting Middleware
Two-layer rate limiting:
  1. IP-level: 200 req/min (protects against DDoS)
  2. User-level: per-plan (10/100/1000 tasks/hour)
     → enforced in API deps.py for task-heavy endpoints
     → this middleware handles raw request rate
"""

import time
import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("goatraw.ratelimit")

# Endpoints exempt from IP rate limiting (health checks, static)
EXEMPT_PATHS = {"/health/", "/health/ready", "/", "/favicon.ico"}

# Endpoints that are expensive — tighter IP limit
HEAVY_PATHS  = {"/task/create", "/agent/run", "/agent/lead-gen",
                "/agent/market-research", "/agent/competitor-analysis",
                "/skills/generate", "/skills/run"}


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory sliding window IP rate limiter.
    Production: replace in-memory dict with Redis pipeline for multi-process.
    """

    def __init__(self, app, requests_per_minute: int = 200, heavy_per_minute: int = 30):
        super().__init__(app)
        self._window   = 60           # seconds
        self._limit    = requests_per_minute
        self._heavy    = heavy_per_minute
        self._buckets: dict[str, list[float]] = {}  # ip → [timestamps]

    def _get_ip(self, request: Request) -> str:
        # Respect Render/Vercel proxy headers
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "0.0.0.0"

    def _is_rate_limited(self, ip: str, path: str) -> tuple[bool, int]:
        now     = time.time()
        cutoff  = now - self._window
        limit   = self._heavy if any(path.startswith(p) for p in HEAVY_PATHS) else self._limit

        if ip not in self._buckets:
            self._buckets[ip] = []

        # Slide window
        self._buckets[ip] = [t for t in self._buckets[ip] if t > cutoff]

        count = len(self._buckets[ip])
        if count >= limit:
            retry_after = int(self._buckets[ip][0] + self._window - now) + 1
            return True, retry_after

        self._buckets[ip].append(now)
        return False, 0

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in EXEMPT_PATHS:
            return await call_next(request)

        ip              = self._get_ip(request)
        limited, retry  = self._is_rate_limited(ip, path)

        if limited:
            logger.warning(f"IP rate limit hit: {ip} → {path}")
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "retry_after_seconds": retry},
                headers={"Retry-After": str(retry), "X-RateLimit-Limit": str(self._limit)},
            )

        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing for observability."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response: Response = await call_next(request)
        elapsed = (time.time() - start) * 1000

        if request.url.path not in EXEMPT_PATHS:
            logger.info(
                f"{request.method} {request.url.path} → {response.status_code} "
                f"({elapsed:.1f}ms) [{request.headers.get('X-Forwarded-For', request.client.host if request.client else '?')}]"
            )
        return response
