"""
mjx.intelligence.planner — Multi-step Task Decomposition & Bounded Execution Planner.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List
from .task_manager import TaskPlan, TaskManager

MAX_PLAN_STEPS = 10


class TaskPlanner:
    """Generates bounded execution plans for complex requests."""

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager

    def plan_request(self, user_prompt: str) -> TaskPlan:
        """
        Decomposes a user prompt into a bounded sequence of steps.
        Enforces execution boundaries and permission flags.
        """
        raw = user_prompt.strip()

        # Split on sequential connectors: "and then", "then", "aur phir", "aur uske baad", ";"
        pattern = re.compile(r"\s*(?:and then|then|aur phir|aur uske baad|;)\s*", re.IGNORECASE)
        segments = [s.strip() for s in pattern.split(raw) if s.strip()]

        if not segments:
            segments = [raw]

        # Enforce maximum steps bound
        segments = segments[:MAX_PLAN_STEPS]

        steps_data: List[Dict[str, Any]] = []
        for i, segment in enumerate(segments):
            action, params, req_approval = self._infer_action(segment)
            steps_data.append({
                "description": segment,
                "action": action,
                "params": params,
                "requires_approval": req_approval,
            })

        return self.task_manager.create_plan(goal=raw, steps_data=steps_data)

    def _infer_action(self, segment: str) -> tuple[str, Dict[str, Any], bool]:
        lower = segment.lower()
        requires_approval = False

        if any(w in lower for w in ["open", "launch", "kholo", "start"]):
            action = "open_app"
            params = {"target": segment}
        elif any(w in lower for w in ["search", "google", "find", "dhundo"]):
            action = "web_search"
            params = {"query": segment}
        elif any(w in lower for w in ["screenshot", "screen"]):
            action = "screen_capture"
            params = {}
            requires_approval = True
        elif any(w in lower for w in ["photo", "camera", "webcam"]):
            action = "camera_capture"
            params = {}
            requires_approval = True
        elif any(w in lower for w in ["write", "save file", "create file"]):
            action = "file_write"
            params = {"details": segment}
            requires_approval = True
        elif any(w in lower for w in ["shutdown", "reboot", "restart"]):
            action = "system_power"
            params = {"action": segment}
            requires_approval = True
        else:
            action = "assistant_action"
            params = {"text": segment}

        return action, params, requires_approval
