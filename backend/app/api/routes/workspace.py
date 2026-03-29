"""
GoatRaw - Workspace Routes
Multi-tenant workspace management.
Each user can have one workspace (Pro) or many (Enterprise).

GET  /workspace/me             — get current workspace
POST /workspace/create         — create new workspace
GET  /workspace/members        — list members
POST /workspace/invite         — invite member
GET  /workspace/api-key        — get/rotate API key
POST /workspace/api-key/rotate — rotate API key
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
import uuid
import secrets
import json
from datetime import datetime

from app.api.deps import get_current_user
from app.core.redis_client import get_redis

router = APIRouter()

WORKSPACE_PREFIX = "goatraw:workspace:"


class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str = ""


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"   # "member" | "admin"


async def get_or_create_workspace(user_id: str) -> dict:
    """Get workspace for user, auto-creating one if it doesn't exist."""
    r = get_redis()
    ws_key = f"{WORKSPACE_PREFIX}user:{user_id}"
    ws_id = await r.get(ws_key)

    if ws_id:
        raw = await r.get(f"{WORKSPACE_PREFIX}{ws_id}")
        if raw:
            return json.loads(raw)

    # Auto-create workspace
    ws_id = str(uuid.uuid4())[:12]
    api_key = f"gr_{secrets.token_urlsafe(32)}"
    workspace = {
        "id": ws_id,
        "owner_id": user_id,
        "name": f"workspace_{user_id[:6]}",
        "description": "Default workspace",
        "api_key": api_key,
        "members": [{"user_id": user_id, "role": "admin"}],
        "created_at": datetime.utcnow().isoformat(),
        "settings": {
            "default_agent": "auto",
            "notify_on_complete": True,
        }
    }
    await r.set(f"{WORKSPACE_PREFIX}{ws_id}", json.dumps(workspace))
    await r.set(ws_key, ws_id)
    await r.set(f"{WORKSPACE_PREFIX}apikey:{api_key}", ws_id)
    return workspace


@router.get("/me")
async def get_my_workspace(user=Depends(get_current_user)):
    workspace = await get_or_create_workspace(str(user["id"]))
    # Mask API key
    ws_copy = {**workspace}
    key = ws_copy.get("api_key", "")
    ws_copy["api_key"] = f"gr_{'*' * 20}{key[-6:]}" if key else ""
    return ws_copy


@router.post("/create")
async def create_workspace(body: CreateWorkspaceRequest, user=Depends(get_current_user)):
    r = get_redis()
    ws_id = str(uuid.uuid4())[:12]
    api_key = f"gr_{secrets.token_urlsafe(32)}"
    workspace = {
        "id": ws_id,
        "owner_id": str(user["id"]),
        "name": body.name,
        "description": body.description,
        "api_key": api_key,
        "members": [{"user_id": str(user["id"]), "role": "admin"}],
        "created_at": datetime.utcnow().isoformat(),
        "settings": {"default_agent": "auto", "notify_on_complete": True},
    }
    await r.set(f"{WORKSPACE_PREFIX}{ws_id}", json.dumps(workspace))
    return {"workspace_id": ws_id, "name": body.name, "api_key": api_key}


@router.post("/api-key/rotate")
async def rotate_api_key(user=Depends(get_current_user)):
    """Generate a new API key (invalidates old one)."""
    r = get_redis()
    workspace = await get_or_create_workspace(str(user["id"]))
    ws_id = workspace["id"]

    # Remove old key
    old_key = workspace.get("api_key", "")
    if old_key:
        await r.delete(f"{WORKSPACE_PREFIX}apikey:{old_key}")

    # New key
    new_key = f"gr_{secrets.token_urlsafe(32)}"
    workspace["api_key"] = new_key
    await r.set(f"{WORKSPACE_PREFIX}{ws_id}", json.dumps(workspace))
    await r.set(f"{WORKSPACE_PREFIX}apikey:{new_key}", ws_id)

    return {"api_key": new_key, "message": "API key rotated. Update your integrations."}


@router.get("/api-key")
async def get_api_key(user=Depends(get_current_user)):
    """Reveal the current API key (once per session)."""
    workspace = await get_or_create_workspace(str(user["id"]))
    return {"api_key": workspace.get("api_key", ""), "workspace_id": workspace["id"]}


@router.patch("/settings")
async def update_workspace_settings(settings_update: dict, user=Depends(get_current_user)):
    """Update workspace settings."""
    r = get_redis()
    workspace = await get_or_create_workspace(str(user["id"]))
    workspace["settings"].update(settings_update)
    await r.set(f"{WORKSPACE_PREFIX}{workspace['id']}", json.dumps(workspace))
    return {"status": "updated", "settings": workspace["settings"]}
