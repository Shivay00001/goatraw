"""
GoatRaw - Memory API Routes
GET  /memory/core              — get core (tier 1) facts
POST /memory/core              — upsert a core memory fact
DELETE /memory/core/{key}      — remove a fact
GET  /memory/session           — get recent session messages
POST /memory/search            — semantic search across deep memory
POST /memory/consolidate       — trigger nightly consolidation manually
GET  /memory/stats             — memory tier stats
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.agents.memory_system import GoatRawMemory, CoreMemory, SessionMemory, DeepMemory
from app.api.deps import get_current_user

router = APIRouter()


class CoreMemoryUpsert(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(..., min_length=1, max_length=1000)
    category: str = Field("knowledge", description="preference | identity | project | knowledge | contact")


class SearchMemoryRequest(BaseModel):
    query: str = Field(..., min_length=3)
    top_k: int = Field(5, ge=1, le=20)


@router.get("/core")
async def get_core_memory(user=Depends(get_current_user)):
    """Get all core (Tier 1) memory facts for the user."""
    core = CoreMemory(str(user["id"]))
    facts = await core.load()
    return {
        "facts": [f.__dict__ for f in facts],
        "count": len(facts),
        "capacity": core.MAX_FACTS,
    }


@router.post("/core")
async def upsert_core_memory(body: CoreMemoryUpsert, user=Depends(get_current_user)):
    """Add or update a core memory fact."""
    core = CoreMemory(str(user["id"]))
    await core.upsert(body.key, body.value, body.category)
    return {"status": "saved", "key": body.key, "category": body.category}


@router.delete("/core/{key}")
async def delete_core_memory(key: str, user=Depends(get_current_user)):
    """Remove a specific fact from core memory."""
    core = CoreMemory(str(user["id"]))
    facts = await core.load()
    original_count = len(facts)
    facts = [f for f in facts if f.key != key]
    if len(facts) == original_count:
        raise HTTPException(status_code=404, detail=f"Memory key '{key}' not found.")
    await core.save(facts)
    return {"status": "deleted", "key": key}


@router.get("/session")
async def get_session_memory(
    session_id: Optional[str] = None,
    last_n: int = 20,
    user=Depends(get_current_user),
):
    """Get recent session (Tier 2) messages."""
    sid = session_id or f"default_{str(user['id'])[:8]}"
    session = SessionMemory(str(user["id"]), sid)
    history = await session.get_history(last_n=last_n)
    return {
        "session_id": sid,
        "messages": [e.__dict__ for e in history],
        "count": len(history),
    }


@router.delete("/session")
async def clear_session_memory(session_id: str, user=Depends(get_current_user)):
    """Clear a session memory."""
    session = SessionMemory(str(user["id"]), session_id)
    await session.clear()
    return {"status": "cleared", "session_id": session_id}


@router.post("/search")
async def search_deep_memory(body: SearchMemoryRequest, user=Depends(get_current_user)):
    """Semantic search across Tier 3 (deep) memory."""
    deep = DeepMemory(str(user["id"]))
    results = await deep.search(body.query, top_k=body.top_k)
    return {
        "query": body.query,
        "results": results,
        "count": len(results),
    }


@router.post("/consolidate")
async def trigger_consolidation(user=Depends(get_current_user)):
    """
    Manually trigger memory consolidation.
    Normally runs nightly automatically.
    """
    memory = GoatRawMemory(str(user["id"]), "manual_consolidation")
    result = await memory.nightly_consolidation()
    return {"status": result, "message": "Memory consolidation complete."}


@router.get("/context")
async def get_full_context(query: Optional[str] = "", user=Depends(get_current_user)):
    """
    Get the full built memory context string exactly as an agent would see it.
    Useful for debugging what the agent knows.
    """
    memory = GoatRawMemory(str(user["id"]), "context_preview")
    ctx = await memory.build_context(query=query)
    return {"context": ctx, "length": len(ctx)}


@router.get("/stats")
async def memory_stats(user=Depends(get_current_user)):
    """Memory tier statistics."""
    from app.core.redis_client import get_redis
    r = get_redis()
    user_id = str(user["id"])

    core_key = f"goatraw:memory:core:{user_id}"
    deep_key = f"goatraw:memory:deep:{user_id}:recent"
    core_raw = await r.get(core_key)
    deep_count = await r.llen(deep_key)

    import json
    core_count = len(json.loads(core_raw)) if core_raw else 0

    return {
        "tier1_core": {"facts": core_count, "capacity": 50},
        "tier3_deep": {"recent_cached": deep_count},
        "user_id": user_id,
    }
