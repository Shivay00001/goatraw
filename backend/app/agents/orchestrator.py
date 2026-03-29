"""
GoatRaw - Agent Orchestrator
The core agent loop: Goal → Plan → Execute → Refine → Output
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from app.agents.memory import AgentMemory
from app.agents.planner import plan_task
from app.agents.executor import AgentExecutor
from app.core.redis_client import set_task_status, set_task_result

logger = logging.getLogger("goatraw.orchestrator")


class GoatRawAgent:
    """
    Stateless agent orchestrator.
    One instance per task execution — do NOT share across requests.
    """

    def __init__(self, task_id: str, goal: str, agent_type: str = "general", context: Optional[dict] = None):
        self.task_id = task_id
        self.goal = goal
        self.agent_type = agent_type
        self.memory = AgentMemory(task_id=task_id, goal=goal, context=context or {})
        self.executor = AgentExecutor(memory=self.memory)

    async def run(self) -> dict:
        """
        Full agent loop execution.
        Updates Redis status at each phase.
        """
        logger.info(f"[{self.task_id}] Agent starting | Goal: {self.goal[:80]}")

        try:
            # ── Phase 1: Planning ──────────────────────────────
            await set_task_status(self.task_id, "planning")
            plan = await plan_task(goal=self.goal, context=self.memory.context)
            self.memory.add("plan", plan)
            logger.info(f"[{self.task_id}] Plan ready: {len(plan.get('steps', []))} steps")

            # ── Phase 2: Execution ─────────────────────────────
            await set_task_status(self.task_id, "executing")
            output = await self.executor.execute_plan(plan)

            # ── Phase 3: Done ──────────────────────────────────
            final_result = {
                "task_id": self.task_id,
                "goal": self.goal,
                "agent_type": self.agent_type,
                "status": "completed",
                "output": output,
                "trace": self.memory.to_dict(),
                "completed_at": datetime.utcnow().isoformat(),
                "steps_taken": self.memory.step_count,
            }

            await set_task_status(self.task_id, "completed")
            await set_task_result(self.task_id, final_result)
            logger.info(f"[{self.task_id}] Agent completed successfully.")
            return final_result

        except Exception as e:
            logger.error(f"[{self.task_id}] Agent failed: {e}", exc_info=True)
            error_result = {
                "task_id": self.task_id,
                "goal": self.goal,
                "status": "failed",
                "error": str(e),
                "trace": self.memory.to_dict(),
                "completed_at": datetime.utcnow().isoformat(),
            }
            await set_task_status(self.task_id, "failed")
            await set_task_result(self.task_id, error_result)
            return error_result


# ─── Specialized Agent Factories ─────────────────────────────────────────────

def create_lead_gen_agent(task_id: str, niche: str, location: str = "", filters: dict = None) -> GoatRawAgent:
    """Factory for Lead Generation Agent."""
    goal = f"""Find business leads in the '{niche}' niche.
Location filter: {location or 'any'}.
Filters: {filters or {}}.
Steps: search for companies, scrape their websites, extract contact details (name, email, phone, website, LinkedIn), filter by relevance, return structured list."""

    return GoatRawAgent(
        task_id=task_id,
        goal=goal,
        agent_type="lead_generation",
        context={"niche": niche, "location": location, "filters": filters or {}},
    )


def create_market_research_agent(task_id: str, topic: str) -> GoatRawAgent:
    """Factory for Market Research Agent."""
    goal = f"""Conduct market research on '{topic}'.
Find: key players, market size estimates, trends, pricing models, customer pain points.
Return structured research report."""

    return GoatRawAgent(
        task_id=task_id,
        goal=goal,
        agent_type="market_research",
        context={"topic": topic},
    )


def create_competitor_analysis_agent(task_id: str, company: str, industry: str) -> GoatRawAgent:
    """Factory for Competitor Analysis Agent."""
    goal = f"""Analyze competitors of '{company}' in the '{industry}' industry.
Find top 5 competitors, their features, pricing, weaknesses, and market positioning."""

    return GoatRawAgent(
        task_id=task_id,
        goal=goal,
        agent_type="competitor_analysis",
        context={"company": company, "industry": industry},
    )
