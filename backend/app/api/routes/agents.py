"""
GoatRaw - Agent API Routes
POST /agent/run           — synchronous execution (short tasks only, <30s)
POST /agent/lead-gen      — specialized lead generation endpoint
POST /agent/market-research
POST /agent/competitor-analysis
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import uuid

from app.agents.orchestrator import (
    GoatRawAgent,
    create_lead_gen_agent,
    create_market_research_agent,
    create_competitor_analysis_agent,
)
from app.core.redis_client import enqueue_task
from app.api.deps import get_current_user, check_rate_limit_for_user

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    goal: str = Field(..., min_length=10, max_length=2000)
    agent_type: str = "general"
    context: Optional[dict] = {}
    sync: bool = Field(False, description="Run synchronously (only for fast tasks)")


class LeadGenRequest(BaseModel):
    niche: str = Field(..., description="Industry or business niche to target")
    location: Optional[str] = Field("", description="City, country, or region")
    filters: Optional[dict] = Field({}, description="Additional filters: company_size, revenue, etc.")


class MarketResearchRequest(BaseModel):
    topic: str = Field(..., description="Market or industry to research")


class CompetitorAnalysisRequest(BaseModel):
    company: str = Field(..., description="Your company or product name")
    industry: str = Field(..., description="Industry vertical")


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/run")
async def run_agent(
    body: AgentRunRequest,
    user=Depends(get_current_user),
):
    """
    Run an agent.
    - sync=False (default): enqueues task, returns task_id for polling
    - sync=True: runs inline (ONLY for very fast goals, risk of timeout)
    """
    await check_rate_limit_for_user(user)
    task_id = str(uuid.uuid4())

    if body.sync:
        # Inline execution — only use for demos or very fast tasks
        agent = GoatRawAgent(
            task_id=task_id,
            goal=body.goal,
            agent_type=body.agent_type,
            context=body.context,
        )
        result = await agent.run()
        return result
    else:
        # Async via queue
        await enqueue_task(task_id, {
            "goal": body.goal,
            "agent_type": body.agent_type,
            "context": body.context or {},
            "user_id": str(user["id"]),
        })
        return {
            "task_id": task_id,
            "status": "queued",
            "poll_url": f"/task/{task_id}",
        }


@router.post("/lead-gen")
async def run_lead_gen_agent(
    body: LeadGenRequest,
    user=Depends(get_current_user),
):
    """Specialized Lead Generation Agent endpoint."""
    await check_rate_limit_for_user(user)
    task_id = str(uuid.uuid4())

    await enqueue_task(task_id, {
        "goal": f"Lead generation for niche: {body.niche}, location: {body.location}",
        "agent_type": "lead_generation",
        "context": {
            "niche": body.niche,
            "location": body.location,
            "filters": body.filters or {},
            "specialized": True,
        },
        "user_id": str(user["id"]),
    })

    return {
        "task_id": task_id,
        "status": "queued",
        "niche": body.niche,
        "poll_url": f"/task/{task_id}",
        "message": f"Lead generation agent launched for '{body.niche}' in '{body.location or 'global'}'",
    }


@router.post("/market-research")
async def run_market_research_agent(
    body: MarketResearchRequest,
    user=Depends(get_current_user),
):
    """Market Research Agent endpoint."""
    await check_rate_limit_for_user(user)
    task_id = str(uuid.uuid4())

    await enqueue_task(task_id, {
        "goal": f"Market research on: {body.topic}",
        "agent_type": "market_research",
        "context": {"topic": body.topic, "specialized": True},
        "user_id": str(user["id"]),
    })

    return {"task_id": task_id, "status": "queued", "poll_url": f"/task/{task_id}"}


@router.post("/competitor-analysis")
async def run_competitor_analysis(
    body: CompetitorAnalysisRequest,
    user=Depends(get_current_user),
):
    """Competitor Analysis Agent endpoint."""
    await check_rate_limit_for_user(user)
    task_id = str(uuid.uuid4())

    await enqueue_task(task_id, {
        "goal": f"Competitor analysis for {body.company} in {body.industry}",
        "agent_type": "competitor_analysis",
        "context": {
            "company": body.company,
            "industry": body.industry,
            "specialized": True,
        },
        "user_id": str(user["id"]),
    })

    return {"task_id": task_id, "status": "queued", "poll_url": f"/task/{task_id}"}
