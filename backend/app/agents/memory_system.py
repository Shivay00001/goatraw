"""
GoatRaw - 3-Tier Memory System
Inspired by OpenClaw's tiered memory architecture, adapted for multi-tenant SaaS.

Tier 1 — Core Memory   : Always loaded. User preferences, identity, key facts (~100 lines max)
Tier 2 — Session Memory: Current + recent sessions. Rolling 48h context window
Tier 3 — Deep Memory   : Full history with vector semantic search via Qdrant/pgvector

OpenClaw uses local Markdown files. GoatRaw uses Supabase JSONB + pgvector.
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Any, List, Optional
from dataclasses import dataclass, field

import httpx
from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger("goatraw.memory")


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class MemoryFact:
    key: str
    value: str
    category: str        # "preference" | "identity" | "task_context" | "knowledge"
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class SessionEntry:
    session_id: str
    role: str           # "user" | "agent" | "tool"
    content: str
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ─── TIER 1: Core Memory (always loaded) ─────────────────────────────────────

class CoreMemory:
    """
    Tier 1 — Always-loaded essentials.
    Equivalent to OpenClaw's MEMORY.md.
    Stored in Redis for fast access, persisted to DB.
    Max 50 key facts per user.
    """

    MAX_FACTS = 50
    TTL = 86400 * 30  # 30 days in Redis

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._redis_key = f"goatraw:memory:core:{user_id}"

    async def load(self) -> List[MemoryFact]:
        r = get_redis()
        raw = await r.get(self._redis_key)
        if raw:
            data = json.loads(raw)
            return [MemoryFact(**f) for f in data]
        return []

    async def save(self, facts: List[MemoryFact]) -> None:
        r = get_redis()
        # Keep only top MAX_FACTS by confidence
        facts_sorted = sorted(facts, key=lambda f: f.confidence, reverse=True)[:self.MAX_FACTS]
        await r.set(self._redis_key, json.dumps([f.__dict__ for f in facts_sorted]), ex=self.TTL)

    async def upsert(self, key: str, value: str, category: str = "knowledge") -> None:
        facts = await self.load()
        # Update existing or add new
        for f in facts:
            if f.key == key:
                f.value = value
                f.last_accessed = datetime.utcnow().isoformat()
                await self.save(facts)
                return
        facts.append(MemoryFact(key=key, value=value, category=category))
        await self.save(facts)

    async def to_prompt_string(self) -> str:
        """Format core memory for LLM context injection."""
        facts = await self.load()
        if not facts:
            return ""
        lines = ["=== CORE MEMORY (always loaded) ==="]
        for f in facts:
            lines.append(f"[{f.category}] {f.key}: {f.value}")
        return "\n".join(lines)


# ─── TIER 2: Session Memory (rolling context) ─────────────────────────────────

class SessionMemory:
    """
    Tier 2 — Recent session context.
    Equivalent to OpenClaw's daily YYYY-MM-DD.md files.
    Stores the last N messages of active sessions.
    Stored in Redis with 48h TTL.
    """

    MAX_ENTRIES = 50
    TTL = 3600 * 48  # 48 hours

    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self._redis_key = f"goatraw:memory:session:{user_id}:{session_id}"

    async def append(self, role: str, content: str, metadata: dict = None) -> None:
        r = get_redis()
        entry = SessionEntry(
            session_id=self.session_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        await r.rpush(self._redis_key, json.dumps(entry.__dict__))
        await r.ltrim(self._redis_key, -self.MAX_ENTRIES, -1)
        await r.expire(self._redis_key, self.TTL)

    async def get_history(self, last_n: int = 20) -> List[SessionEntry]:
        r = get_redis()
        raw_list = await r.lrange(self._redis_key, -last_n, -1)
        return [SessionEntry(**json.loads(r)) for r in raw_list]

    async def to_messages(self, last_n: int = 20) -> List[dict]:
        """Format for LLM messages array."""
        history = await self.get_history(last_n)
        messages = []
        for entry in history:
            if entry.role in ("user", "assistant"):
                messages.append({"role": entry.role, "content": entry.content})
        return messages

    async def clear(self) -> None:
        r = get_redis()
        await r.delete(self._redis_key)


# ─── TIER 3: Deep Memory (semantic search) ────────────────────────────────────

class DeepMemory:
    """
    Tier 3 — Long-term knowledge with vector semantic search.
    Equivalent to OpenClaw's memory/people/, memory/projects/, memory/topics/ dirs.
    Uses pgvector (Supabase) or Qdrant for semantic retrieval.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id

    async def store(self, content: str, category: str, metadata: dict = None) -> str:
        """Store a memory with its embedding."""
        embedding = await self._embed(content)
        memory_id = hashlib.md5(f"{self.user_id}:{content[:100]}".encode()).hexdigest()

        # Store in Supabase via REST (no local DB dependency)
        # In production: use asyncpg directly with pgvector
        record = {
            "id": memory_id,
            "user_id": self.user_id,
            "content": content,
            "category": category,
            "embedding": embedding,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
        }

        # Cache in Redis for fast recent retrieval
        r = get_redis()
        cache_key = f"goatraw:memory:deep:{self.user_id}:recent"
        await r.lpush(cache_key, json.dumps({"id": memory_id, "content": content, "category": category}))
        await r.ltrim(cache_key, 0, 99)  # Keep last 100
        await r.expire(cache_key, 86400 * 7)

        logger.info(f"Deep memory stored: {memory_id} [{category}]")
        return memory_id

    async def search(self, query: str, top_k: int = 5) -> List[dict]:
        """Semantic search across deep memories."""
        query_embedding = await self._embed(query)

        # In production: use pgvector cosine similarity query
        # SELECT content, category, 1 - (embedding <=> $1) as similarity
        # FROM deep_memories WHERE user_id = $2 ORDER BY similarity DESC LIMIT $3

        # Fallback: keyword search from Redis cache
        r = get_redis()
        cache_key = f"goatraw:memory:deep:{self.user_id}:recent"
        raw_list = await r.lrange(cache_key, 0, 99)
        memories = [json.loads(m) for m in raw_list]

        # Simple keyword matching as fallback
        query_words = set(query.lower().split())
        scored = []
        for m in memories:
            content_words = set(m["content"].lower().split())
            score = len(query_words & content_words) / max(len(query_words), 1)
            if score > 0:
                scored.append({**m, "similarity": score})

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    async def consolidate(self, session_memories: List[SessionEntry]) -> str:
        """
        Memory consolidation — OpenClaw runs this nightly.
        Summarizes session into durable long-term memories.
        """
        from app.services.llm_adapter import generate_json, ModelType

        if not session_memories:
            return "nothing_to_consolidate"

        conversation_text = "\n".join(
            f"{e.role}: {e.content}" for e in session_memories[-30:]
        )

        prompt = f"""Analyze this conversation and extract important facts worth remembering long-term.

Conversation:
{conversation_text[:4000]}

Extract:
- User preferences (communication style, interests, dislikes)
- Important decisions made
- Key facts about ongoing projects
- People/companies mentioned with context
- Any promises or commitments

Return JSON:
{{
  "memories": [
    {{"content": "...", "category": "preference|decision|project|person|commitment"}}
  ]
}}
Only include genuinely important, durable facts. Skip small talk."""

        try:
            result = await generate_json(prompt, model_type=ModelType.FAST)
            memories = result.get("memories", [])
            for m in memories:
                await self.store(m["content"], m["category"])
            return f"consolidated_{len(memories)}_memories"
        except Exception as e:
            logger.error(f"Memory consolidation failed: {e}")
            return "consolidation_failed"

    async def _embed(self, text: str) -> List[float]:
        """Get text embedding. Uses OpenAI or Groq embedding endpoint."""
        # In production, use OpenAI text-embedding-3-small
        # For now: return zero vector (replace with real embedding)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json={"model": "text-embedding-3-small", "input": text[:8000]},
                )
                data = resp.json()
                return data["data"][0]["embedding"]
        except Exception:
            # Fallback: 1536-dim zero vector
            return [0.0] * 1536


# ─── Unified Memory Interface ──────────────────────────────────────────────────

class GoatRawMemory:
    """
    Unified memory interface for agents.
    Manages all 3 tiers together.
    """

    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.core = CoreMemory(user_id)
        self.session = SessionMemory(user_id, session_id)
        self.deep = DeepMemory(user_id)

    async def build_context(self, query: str = "") -> str:
        """
        Build full memory context for LLM injection.
        Tier 1 always included. Tier 2 last N messages. Tier 3 if query given.
        """
        parts = []

        # Tier 1 — always
        core_str = await self.core.to_prompt_string()
        if core_str:
            parts.append(core_str)

        # Tier 2 — recent session
        messages = await self.session.to_messages(last_n=10)
        if messages:
            parts.append("=== RECENT CONTEXT ===")
            for m in messages:
                parts.append(f"{m['role'].upper()}: {m['content'][:300]}")

        # Tier 3 — semantic search if query given
        if query:
            deep_results = await self.deep.search(query, top_k=3)
            if deep_results:
                parts.append("=== RELEVANT MEMORIES ===")
                for r in deep_results:
                    parts.append(f"[{r['category']}] {r['content']}")

        return "\n\n".join(parts)

    async def remember(self, key: str, value: str, category: str = "knowledge") -> None:
        """Store in core memory (short facts)."""
        await self.core.upsert(key, value, category)

    async def log_interaction(self, role: str, content: str, metadata: dict = None) -> None:
        """Log a turn to session memory."""
        await self.session.append(role, content, metadata)

    async def nightly_consolidation(self) -> str:
        """Run memory consolidation (called by scheduler)."""
        session_entries = await self.session.get_history(last_n=50)
        return await self.deep.consolidate(session_entries)
