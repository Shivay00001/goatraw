"""
GoatRaw - Agent Planner
Breaks a high-level goal into ordered, executable steps with tool assignments.
"""

import json
import logging
from typing import List
from app.services.llm_adapter import generate_json, ModelType
from app.agents.tools import get_tool_descriptions

logger = logging.getLogger("goatraw.planner")

PLANNER_SYSTEM_PROMPT = """You are GoatRaw's task planner. Your job is to decompose a business automation goal into a precise sequence of executable steps.

Available tools:
{tool_descriptions}

Rules:
1. Each step MUST use one of the available tools.
2. Steps must be ordered — later steps can reference results from earlier ones.
3. Keep the plan minimal — max 8 steps.
4. Be specific: include exact search queries, URLs, or parameters where possible.
5. Output ONLY valid JSON.

Output format:
{{
  "goal_summary": "brief restatement of the goal",
  "steps": [
    {{
      "step_id": 1,
      "description": "what this step does",
      "tool": "tool_name",
      "params": {{...}},
      "depends_on": []
    }}
  ]
}}"""


async def plan_task(goal: str, context: dict = None) -> dict:
    """
    Generate an execution plan for the given goal.
    Returns a structured plan with ordered steps.
    """
    context_str = json.dumps(context or {})

    prompt = f"""Create an execution plan for this goal:

Goal: {goal}

Additional context: {context_str}

Generate a step-by-step plan using the available tools.
Each step must have a clear tool assignment and parameters."""

    system = PLANNER_SYSTEM_PROMPT.format(
        tool_descriptions=get_tool_descriptions()
    )

    logger.info(f"Planning task: {goal[:80]}...")

    try:
        plan = await generate_json(
            prompt=prompt,
            model_type=ModelType.FAST,
            system_prompt=system,
        )
        logger.info(f"Plan generated: {len(plan.get('steps', []))} steps")
        return plan
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        # Fallback minimal plan
        return {
            "goal_summary": goal,
            "steps": [
                {
                    "step_id": 1,
                    "description": f"Search for information about: {goal}",
                    "tool": "search_web",
                    "params": {"query": goal, "num_results": 5},
                    "depends_on": [],
                }
            ],
        }


async def replan_task(goal: str, completed_steps: list, error: str) -> dict:
    """
    Regenerate remaining steps when an error occurs mid-execution.
    """
    prompt = f"""The following task failed mid-execution. Generate a revised plan for the remaining work.

Original goal: {goal}
Completed steps: {json.dumps(completed_steps)}
Error encountered: {error}

Generate a corrected plan to complete the remaining work."""

    system = PLANNER_SYSTEM_PROMPT.format(
        tool_descriptions=get_tool_descriptions()
    )

    return await generate_json(prompt, model_type=ModelType.SMART, system_prompt=system)
