"""
GoatRaw - Agent Memory System
Stores context, intermediate results, and task history for agent loops.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("goatraw.memory")


@dataclass
class MemoryEntry:
    step: int
    type: str          # "plan" | "tool_call" | "tool_result" | "thought" | "output"
    content: Any
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class AgentMemory:
    """
    In-process memory for a single agent execution.
    Stores the full trace: plan, tool calls, results, thoughts.
    """

    def __init__(self, task_id: str, goal: str, context: Optional[dict] = None):
        self.task_id = task_id
        self.goal = goal
        self.context = context or {}
        self.entries: List[MemoryEntry] = []
        self._step = 0

    def add(self, type: str, content: Any) -> None:
        self._step += 1
        entry = MemoryEntry(step=self._step, type=type, content=content)
        self.entries.append(entry)
        logger.debug(f"[{self.task_id}] Memory step {self._step}: {type}")

    def get_plan(self) -> Optional[dict]:
        for e in self.entries:
            if e.type == "plan":
                return e.content
        return None

    def get_tool_results(self) -> List[dict]:
        return [
            {"step": e.step, "result": e.content}
            for e in self.entries
            if e.type == "tool_result"
        ]

    def get_all_results(self) -> List[Any]:
        return [e.content for e in self.entries if e.type == "tool_result"]

    def get_context_for_llm(self, max_entries: int = 10) -> str:
        """Returns a condensed context string for LLM prompts."""
        lines = [f"Goal: {self.goal}"]
        recent = self.entries[-max_entries:]
        for e in recent:
            content_str = json.dumps(e.content) if not isinstance(e.content, str) else e.content
            lines.append(f"[Step {e.step} - {e.type}]: {content_str[:500]}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "context": self.context,
            "entries": [
                {
                    "step": e.step,
                    "type": e.type,
                    "content": e.content,
                    "timestamp": e.timestamp,
                }
                for e in self.entries
            ],
        }

    @property
    def step_count(self) -> int:
        return self._step
