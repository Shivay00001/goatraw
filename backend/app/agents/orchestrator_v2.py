"""
GoatRaw - Full Agent Orchestrator v2
Now with all OpenClaw capabilities:
- 3-tier memory (Core / Session / Deep)
- Skill system
- Multi-step planning with replanning
- Tool execution with browser support
- Self-improving (skill generation)
- Smart monitoring (only notify on change)
- Sub-agent delegation
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.agents.memory_system import GoatRawMemory
from app.agents.skill_system import skill_registry, SkillDefinition
from app.agents.planner import plan_task, replan_task
from app.agents.executor import AgentExecutor
from app.agents.memory import AgentMemory
from app.core.redis_client import set_task_status, set_task_result
from app.services.llm_adapter import generate, generate_json, ModelType

logger = logging.getLogger("goatraw.orchestrator_v2")


class GoatRawAgentV2:
    """
    Full-featured GoatRaw agent with all OpenClaw-inspired capabilities.
    Stateless per execution, but reads/writes to persistent memory store.
    """

    def __init__(
        self,
        task_id: str,
        goal: str,
        user_id: str,
        agent_type: str = "general",
        context: Optional[dict] = None,
        skill_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        self.task_id = task_id
        self.goal = goal
        self.user_id = user_id
        self.agent_type = agent_type
        self.context = context or {}
        self.skill_id = skill_id
        self.workspace_id = workspace_id or user_id
        self.session_id = f"task_{task_id}"

        # Memory
        self.memory = GoatRawMemory(user_id=user_id, session_id=self.session_id)
        self.trace_memory = AgentMemory(task_id=task_id, goal=goal, context=context)
        self.executor = AgentExecutor(memory=self.trace_memory)

    async def run(self) -> dict:
        """Full agent execution with memory, skills, and planning."""
        logger.info(f"[{self.task_id}] GoatRaw Agent v2 | {self.agent_type} | {self.goal[:80]}")

        try:
            # ── Load memory context ────────────────────────────────────────────
            await set_task_status(self.task_id, "planning")
            memory_context = await self.memory.build_context(query=self.goal)
            if memory_context:
                self.context["memory_context"] = memory_context[:2000]

            # ── Log this interaction to session memory ────────────────────────
            await self.memory.log_interaction("user", self.goal, metadata={"task_id": self.task_id})

            # ── Route: skill-based or general planning ─────────────────────────
            if self.skill_id:
                output = await self._run_with_skill()
            else:
                output = await self._run_with_planner()

            # ── Extract memory from output ─────────────────────────────────────
            await self._extract_and_store_memory(output)

            # ── Log result to session ──────────────────────────────────────────
            summary = output.get("summary", "Task completed")
            await self.memory.log_interaction("agent", summary, metadata={"task_id": self.task_id, "status": output.get("status")})

            final_result = {
                "task_id": self.task_id,
                "goal": self.goal,
                "agent_type": self.agent_type,
                "skill_id": self.skill_id,
                "status": "completed",
                "output": output,
                "trace": self.trace_memory.to_dict(),
                "completed_at": datetime.utcnow().isoformat(),
                "steps_taken": self.trace_memory.step_count,
            }

            await set_task_status(self.task_id, "completed")
            await set_task_result(self.task_id, final_result)
            return final_result

        except Exception as e:
            logger.error(f"[{self.task_id}] Agent v2 failed: {e}", exc_info=True)
            error_result = {
                "task_id": self.task_id,
                "goal": self.goal,
                "status": "failed",
                "error": str(e),
                "trace": self.trace_memory.to_dict(),
                "completed_at": datetime.utcnow().isoformat(),
            }
            await set_task_status(self.task_id, "failed")
            await set_task_result(self.task_id, error_result)
            return error_result

    async def _run_with_skill(self) -> dict:
        """Execute a predefined skill."""
        skill = await skill_registry.get_skill(self.skill_id, self.workspace_id)
        if not skill:
            logger.warning(f"Skill {self.skill_id} not found, falling back to planner")
            return await self._run_with_planner()

        logger.info(f"[{self.task_id}] Running skill: {skill.name}")
        self.trace_memory.add("thought", f"Executing skill: {skill.name}")

        # Convert skill steps to plan format
        steps = []
        for i, step in enumerate(skill.steps):
            # Resolve params with input values
            resolved_params = self._resolve_skill_params(step.params_template, self.context)
            steps.append({
                "step_id": i + 1,
                "description": step.description or f"Skill step: {step.tool}",
                "tool": step.tool,
                "params": resolved_params,
                "depends_on": list(range(i)),
            })

        plan = {"goal_summary": skill.description, "steps": steps}
        self.trace_memory.add("plan", plan)

        await set_task_status(self.task_id, "executing")
        return await self.executor.execute_plan(plan)

    def _resolve_skill_params(self, params_template: dict, inputs: dict) -> dict:
        """Resolve {input.field} references in skill step params."""
        def resolve_value(v):
            if isinstance(v, str) and "{input." in v:
                for k, val in inputs.items():
                    v = v.replace(f"{{input.{k}}}", str(val))
            return v

        return {k: resolve_value(v) for k, v in params_template.items()}

    async def _run_with_planner(self) -> dict:
        """Full plan → execute → synthesize flow."""
        plan = await plan_task(goal=self.goal, context=self.context)
        self.trace_memory.add("plan", plan)

        await set_task_status(self.task_id, "executing")
        output = await self.executor.execute_plan(plan)

        # Check if we need replanning
        if output.get("status") == "failed" and self.trace_memory.step_count < 3:
            logger.info(f"[{self.task_id}] Initial execution failed, attempting replan...")
            await set_task_status(self.task_id, "planning")
            revised_plan = await replan_task(
                goal=self.goal,
                completed_steps=self.trace_memory.get_tool_results(),
                error=output.get("error", "unknown"),
            )
            self.trace_memory.add("plan", revised_plan)
            await set_task_status(self.task_id, "executing")
            output = await self.executor.execute_plan(revised_plan)

        return output

    async def _extract_and_store_memory(self, output: dict) -> None:
        """
        Smart memory extraction from task output.
        Store durable facts in core memory.
        """
        try:
            data = output.get("data", {})
            if not data:
                return

            prompt = f"""Extract 1-3 key facts worth remembering from this task result.
Goal was: {self.goal}
Result: {json.dumps(data)[:1000]}

Return JSON: {{"facts": [{{"key": "...", "value": "...", "category": "preference|project|knowledge|contact"}}]}}
Only include genuinely memorable, reusable facts. Return empty list if nothing notable."""

            result = await generate_json(prompt, model_type=ModelType.FAST)
            for fact in result.get("facts", [])[:3]:
                await self.memory.remember(fact["key"], fact["value"], fact.get("category", "knowledge"))

        except Exception as e:
            logger.debug(f"Memory extraction failed (non-critical): {e}")


# ─── Sub-Agent Delegation ─────────────────────────────────────────────────────

class SubAgentDelegator:
    """
    OpenClaw: "Expert agents — delegate complex tasks to specialized sub-agents"
    GoatRaw: Routes to specialized GoatRaw agents based on task analysis.
    """

    AGENT_TYPES = {
        "lead_generation": "Find and qualify business leads",
        "market_research": "Research markets, industries, trends",
        "competitor_analysis": "Analyze competitors features, pricing, positioning",
        "data_extraction": "Extract structured data from web sources",
        "outreach_drafting": "Draft personalized outreach messages",
        "website_audit": "Audit websites for SEO, copy, CTA quality",
    }

    async def route(self, goal: str, user_id: str) -> str:
        """Determine best agent type for the goal."""
        agent_list = "\n".join(f"- {k}: {v}" for k, v in self.AGENT_TYPES.items())
        prompt = f"""Classify this goal into the best agent type:

Goal: {goal}

Agent types:
{agent_list}

Return JSON: {{"agent_type": "...", "confidence": 0.0-1.0, "reason": "..."}}"""

        try:
            result = await generate_json(prompt, model_type=ModelType.FAST)
            agent_type = result.get("agent_type", "general")
            if agent_type not in self.AGENT_TYPES:
                agent_type = "general"
            return agent_type
        except Exception:
            return "general"

    async def delegate(self, goal: str, user_id: str, task_id: str, context: dict = None) -> GoatRawAgentV2:
        """Create the right agent for the job."""
        agent_type = await self.route(goal, user_id)
        return GoatRawAgentV2(
            task_id=task_id,
            goal=goal,
            user_id=user_id,
            agent_type=agent_type,
            context=context or {},
        )


delegator = SubAgentDelegator()


# ─── Smart Monitoring Agent ────────────────────────────────────────────────────

class SmartMonitor:
    """
    OpenClaw: "Smart background checks — monitoring tasks only notify when something new is found"
    GoatRaw: Compare new result against last result hash, only trigger if changed.
    """

    PREFIX = "goatraw:monitor:last:"

    async def check_and_notify(self, monitor_id: str, new_result: dict, user_id: str) -> bool:
        """Returns True if change detected (notification should fire)."""
        import hashlib
        r = get_redis()

        # Hash the meaningful content
        content_str = json.dumps(new_result.get("data", new_result), sort_keys=True)
        new_hash = hashlib.md5(content_str.encode()).hexdigest()

        last_hash = await r.get(f"{self.PREFIX}{user_id}:{monitor_id}")

        if last_hash == new_hash:
            logger.debug(f"Monitor {monitor_id}: no change detected")
            return False  # Silent OK

        # Save new hash
        await r.set(f"{self.PREFIX}{user_id}:{monitor_id}", new_hash, ex=86400 * 30)
        logger.info(f"Monitor {monitor_id}: CHANGE DETECTED — notification firing")
        return True  # Change detected, notify


from app.core.redis_client import get_redis
smart_monitor = SmartMonitor()
