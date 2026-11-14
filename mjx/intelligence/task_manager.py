"""
mjx.intelligence.task_manager — Persistent Task State Engine with Bounded Lifecycle.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskStep:
    id: str
    description: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    requires_approval: bool = False
    approved: bool = False


@dataclass
class TaskPlan:
    task_id: str
    goal: str
    steps: List[TaskStep]
    status: TaskStatus = TaskStatus.PENDING
    current_step_index: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def current_step(self) -> Optional[TaskStep]:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    @property
    def is_finished(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)


class TaskManager:
    """Manages multi-step autonomous task plans, pauses, resumes, and cancellations."""

    def __init__(self):
        self._plans: Dict[str, TaskPlan] = {}

    def create_plan(self, goal: str, steps_data: List[Dict[str, Any]]) -> TaskPlan:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        steps = []
        for i, s in enumerate(steps_data):
            steps.append(
                TaskStep(
                    id=f"{task_id}_step_{i+1}",
                    description=s.get("description", f"Step {i+1}"),
                    action=s.get("action", ""),
                    params=s.get("params", {}),
                    requires_approval=s.get("requires_approval", False),
                )
            )

        plan = TaskPlan(task_id=task_id, goal=goal, steps=steps)
        self._plans[task_id] = plan
        return plan

    def get_plan(self, task_id: str) -> Optional[TaskPlan]:
        return self._plans.get(task_id)

    def advance_step(self, task_id: str, step_result: str, success: bool = True, error: Optional[str] = None) -> TaskPlan:
        plan = self._plans.get(task_id)
        if not plan:
            raise KeyError(f"Task plan '{task_id}' not found")

        curr = plan.current_step
        if curr:
            curr.result = step_result
            if success:
                curr.status = TaskStatus.COMPLETED
                plan.current_step_index += 1
                if plan.current_step_index >= len(plan.steps):
                    plan.status = TaskStatus.COMPLETED
            else:
                curr.status = TaskStatus.FAILED
                curr.error = error or "Execution failed"
                plan.status = TaskStatus.FAILED

        plan.updated_at = time.time()
        return plan

    def cancel_plan(self, task_id: str, reason: str = "User cancelled") -> bool:
        plan = self._plans.get(task_id)
        if not plan:
            return False
        plan.status = TaskStatus.CANCELLED
        if plan.current_step:
            plan.current_step.status = TaskStatus.CANCELLED
            plan.current_step.error = reason
        plan.updated_at = time.time()
        return True

    def pause_plan(self, task_id: str) -> bool:
        plan = self._plans.get(task_id)
        if not plan or plan.is_finished:
            return False
        plan.status = TaskStatus.PAUSED
        if plan.current_step:
            plan.current_step.status = TaskStatus.PAUSED
        return True

    def resume_plan(self, task_id: str) -> bool:
        plan = self._plans.get(task_id)
        if not plan or plan.status != TaskStatus.PAUSED:
            return False
        plan.status = TaskStatus.RUNNING
        if plan.current_step:
            plan.current_step.status = TaskStatus.RUNNING
        return True

    def list_active_plans(self) -> List[TaskPlan]:
        return [p for p in self._plans.values() if not p.is_finished]
