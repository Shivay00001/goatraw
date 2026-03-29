"""
GoatRaw - Agent Executor
Executes a plan step by step, calls tools, handles errors, and synthesizes output.
"""

import json
import logging
from typing import Any, Dict, Optional
from app.agents.memory import AgentMemory
from app.agents.tools import execute_tool
from app.services.llm_adapter import generate, generate_json, ModelType
from app.core.config import settings

logger = logging.getLogger("goatraw.executor")


SYNTHESIZER_SYSTEM_PROMPT = """You are GoatRaw's output synthesizer. You receive the results of an automated agent task and produce a clean, structured, actionable final output.

Rules:
- Be factual and precise
- Remove noise and irrelevant data
- Format output clearly
- If leads/contacts are found, structure them as a list
- If data is extracted, organize it logically
- Output ONLY valid JSON"""


class AgentExecutor:
    """
    Executes a task plan step by step.
    Handles tool calls, error recovery, and final synthesis.
    """

    def __init__(self, memory: AgentMemory):
        self.memory = memory
        self.max_steps = settings.MAX_TASK_STEPS

    async def execute_plan(self, plan: dict) -> dict:
        """
        Execute all steps in a plan.
        Returns the final synthesized output.
        """
        steps = plan.get("steps", [])
        step_results: Dict[int, Any] = {}

        logger.info(f"[{self.memory.task_id}] Executing {len(steps)} steps...")

        for step in steps:
            if self.memory.step_count >= self.max_steps:
                logger.warning(f"[{self.memory.task_id}] Max steps reached, stopping.")
                break

            step_id = step["step_id"]
            tool_name = step["tool"]
            params = step.get("params", {})

            # Resolve param references to previous step results
            params = self._resolve_params(params, step_results)

            # Log thought about this step
            self.memory.add("thought", f"Executing step {step_id}: {step.get('description', '')}")
            self.memory.add("tool_call", {"tool": tool_name, "params": params})

            # Execute the tool
            try:
                result = await execute_tool(tool_name, params)
                step_results[step_id] = result
                self.memory.add("tool_result", result)
                logger.info(f"[{self.memory.task_id}] Step {step_id} completed: {tool_name}")
            except Exception as e:
                error_result = {"error": str(e), "status": "error"}
                step_results[step_id] = error_result
                self.memory.add("tool_result", error_result)
                logger.error(f"[{self.memory.task_id}] Step {step_id} failed: {e}")

        # Synthesize final output
        final_output = await self._synthesize_output(plan)
        self.memory.add("output", final_output)

        return final_output

    def _resolve_params(self, params: dict, step_results: dict) -> dict:
        """
        Resolve template references like {{step_1_result}} in params.
        Simple string interpolation for now.
        """
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                ref_key = v[2:-2].strip()
                # Parse ref like "step_1_result.content"
                parts = ref_key.split(".")
                step_ref = int(parts[0].replace("step_", "").replace("_result", ""))
                if step_ref in step_results:
                    val = step_results[step_ref]
                    for part in parts[1:]:
                        if isinstance(val, dict):
                            val = val.get(part, "")
                    resolved[k] = val
                else:
                    resolved[k] = v
            else:
                resolved[k] = v
        return resolved

    async def _synthesize_output(self, plan: dict) -> dict:
        """
        Use LLM to synthesize all tool results into a clean final output.
        """
        context = self.memory.get_context_for_llm(max_entries=20)
        all_results = self.memory.get_all_results()

        prompt = f"""Synthesize the following agent execution results into a final structured output.

Original Goal: {self.memory.goal}

Execution Context:
{context}

All Tool Results:
{json.dumps(all_results, indent=2)[:6000]}

Produce a clean, structured JSON output with:
- "summary": brief summary of what was accomplished
- "status": "success" | "partial" | "failed"
- "data": the main result data (leads, information, extracted data, etc.)
- "stats": any relevant metrics (count, etc.)
- "next_steps": optional list of recommended follow-up actions"""

        try:
            result = await generate_json(
                prompt=prompt,
                model_type=ModelType.SMART,
                system_prompt=SYNTHESIZER_SYSTEM_PROMPT,
            )
            return result
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return {
                "summary": f"Task completed with {len(all_results)} steps",
                "status": "partial",
                "data": all_results,
                "stats": {"steps_executed": self.memory.step_count},
                "next_steps": [],
            }
