"""
mjx.intelligence.context_engine — Context Aggregation, Relevance Ranking & Memory Injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from mjx.memory import MemoryRepository, MemoryItem


@dataclass
class WorkingContext:
    user_prompt: str
    recent_messages: List[Dict[str, str]] = field(default_factory=list)
    relevant_memories: List[Dict[str, Any]] = field(default_factory=list)
    active_task: Optional[Dict[str, Any]] = None
    system_state: Dict[str, Any] = field(default_factory=dict)
    personality_mode: str = "casual_friend"
    current_emotion: str = "neutral"

    def format_context_prompt(self, max_memory_items: int = 5) -> str:
        """Render a concise context block for LLM inference."""
        lines = []

        if self.relevant_memories:
            lines.append("### RELEVANT LOCAL MEMORIES:")
            for m in self.relevant_memories[:max_memory_items]:
                key = m.get("key", "")
                val = m.get("value", "")
                lines.append(f"- {key}: {val}")

        if self.active_task:
            lines.append(f"### ACTIVE TASK: {self.active_task.get('goal', '')} (Status: {self.active_task.get('status', '')})")

        return "\n".join(lines)


class ContextEngine:
    """Builds and filters context for the intelligence core."""

    def __init__(self, memory_repo: Optional[MemoryRepository] = None):
        self.memory_repo = memory_repo

    def assemble_context(
        self,
        user_prompt: str,
        conversation_id: Optional[str] = None,
        active_task_dict: Optional[Dict[str, Any]] = None,
        emotion: str = "neutral",
        personality_mode: str = "casual_friend",
    ) -> WorkingContext:
        recent_msgs = []
        relevant_mems = []

        if self.memory_repo:
            # 1. Fetch recent conversation messages
            if conversation_id:
                recent_msgs = self.memory_repo.get_messages(conversation_id, limit=6)

            # 2. Retrieve relevant memories via FTS5
            try:
                search_results = self.memory_repo.search_engine.search_memories(user_prompt, limit=5)
                relevant_mems = search_results
            except Exception:
                pass

        return WorkingContext(
            user_prompt=user_prompt,
            recent_messages=recent_msgs,
            relevant_memories=relevant_mems,
            active_task=active_task_dict,
            personality_mode=personality_mode,
            current_emotion=emotion,
        )
