"""
GoatRaw — Agent Router
Maps agent_type → specialised agent class.
Single place to add new agent types.
"""

import uuid
from typing import Optional

from app.agents.orchestrator_v2        import GoatRawAgentV2
from app.agents.lead_gen_agent         import LeadGenAgent
from app.agents.competitor_agent       import CompetitorAnalysisAgent
from app.agents.market_research_agent  import MarketResearchAgent


async def create_agent(
    task_id:    str,
    goal:       str,
    agent_type: str,
    user_id:    str,
    context:    dict,
    skill_id:   Optional[str] = None,
):
    """
    Factory: return the right agent for the job.
    All agents implement .run() → dict.
    """

    # ── Specialised agents (faster, more accurate) ────────────
    if agent_type == "lead_generation" and context.get("specialized"):
        return LeadGenAgent(
            task_id  = task_id,
            niche    = context.get("niche", goal),
            location = context.get("location", ""),
            filters  = context.get("filters", {}),
            max_leads= context.get("max_leads", 20),
        )

    if agent_type == "competitor_analysis" and context.get("specialized"):
        return CompetitorAnalysisAgent(
            task_id         = task_id,
            competitor_name = context.get("competitor_name", goal),
            your_product    = context.get("your_product", "our product"),
            industry        = context.get("industry", ""),
        )

    if agent_type == "market_research" and context.get("specialized"):
        return MarketResearchAgent(
            task_id = task_id,
            topic   = context.get("topic", goal),
            focus   = context.get("focus", "general"),
        )

    # ── General purpose with skill support ────────────────────
    return GoatRawAgentV2(
        task_id    = task_id,
        goal       = goal,
        user_id    = user_id,
        agent_type = agent_type,
        context    = context,
        skill_id   = skill_id,
    )
