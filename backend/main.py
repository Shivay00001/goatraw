"""
GoatRaw v2 — FastAPI Application (Final Complete)
All routes, middleware, WebSocket, payments, admin wired.
"""
import time, logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config   import settings
from app.core.database import init_db
from app.core.redis_client import init_redis

from app.api.routes import (
    health, users, tasks, agents, channels,
    skills, memory_api, heartbeat_api,
    cron_api, usage, workspace, admin,
    payments, websocket,
)
from app.api.routes import export as export_routes
from app.middlewares.rate_limit import IPRateLimitMiddleware, RequestLoggingMiddleware
from app.core.observability import obs_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("goatraw")

app = FastAPI(
    title="GoatRaw API", version="2.0.0",
    docs_url="/docs" if settings.DEBUG else None, redoc_url=None,
)

# Middleware
app.add_middleware(CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])
app.add_middleware(IPRateLimitMiddleware, requests_per_minute=200, heavy_per_minute=30)
app.add_middleware(RequestLoggingMiddleware)

@app.on_event("startup")
async def startup():
    await init_db()
    await init_redis()
    import app.agents.tools_extended  # noqa — register extended tools
    # Start WebSocket Redis listener in background
    import asyncio
    asyncio.create_task(websocket.redis_event_listener())
    logger.info("GoatRaw v2 ready ✓")

@app.on_event("shutdown")
async def shutdown():
    logger.info("GoatRaw shutting down.")

# Routes
app.include_router(health.router,           prefix="/health",     tags=["Health"])
app.include_router(users.router,            prefix="/users",      tags=["Auth"])
app.include_router(workspace.router,        prefix="/workspace",  tags=["Workspace"])
app.include_router(tasks.router,            prefix="/task",       tags=["Tasks"])
app.include_router(agents.router,           prefix="/agent",      tags=["Agents"])
app.include_router(skills.router,           prefix="/skills",     tags=["Skills"])
app.include_router(memory_api.router,       prefix="/memory",     tags=["Memory"])
app.include_router(heartbeat_api.router,    prefix="/heartbeat",  tags=["Heartbeat"])
app.include_router(cron_api.router,         prefix="/cron",       tags=["Cron"])
app.include_router(usage.router,            prefix="/usage",      tags=["Usage"])
app.include_router(export_routes.router,    prefix="/export",     tags=["Export"])
app.include_router(payments.router,         prefix="/payments",   tags=["Payments"])
app.include_router(admin.router,            prefix="/admin",      tags=["Admin"])
app.include_router(obs_router,              prefix="/internal",   tags=["Observability"])
app.include_router(websocket.router,        prefix="",            tags=["WebSocket"])
app.include_router(channels.router,         prefix="",            tags=["Channels"])

@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    logger.error(f"Unhandled: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": str(exc)})

@app.get("/")
async def root():
    return {"service": "GoatRaw API", "version": "2.0.0", "status": "running"}
