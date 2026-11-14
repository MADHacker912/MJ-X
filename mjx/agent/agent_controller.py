"""
mjx.agent.agent_controller — Autonomous Desktop Agent Orchestrator (Project GHOST).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from mjx.agent.action_executor import DesktopActionExecutor, ExecutionResult
from mjx.agent.action_planner import ActionPrimitive, DesktopActionPlanner, DesktopActionStep
from mjx.agent.computer_vision import DesktopPerception
from mjx.agent.execution_verifier import DesktopExecutionVerifier, VerificationOutcome
from mjx.agent.safety_guard import AgentSafetyGuard, SafetyCheckResult
from mjx.security.permissions import PermissionManager


@dataclass
class AgentRunReport:
    goal: str
    steps_executed: int
    success: bool
    message: str
    details: List[ExecutionResult]


class DesktopAgentController:
    """Orchestrates perception, safety inspection, planning, action dispatch, and verification."""

    def __init__(
        self,
        permission_mgr: Optional[PermissionManager] = None,
        custom_dispatcher: Optional[Callable[[DesktopActionStep, int, int], bool]] = None,
        screen_width: int = 1920,
        screen_height: int = 1080,
    ):
        self.safety_guard = AgentSafetyGuard(permission_mgr)
        self.perception = DesktopPerception(screen_width, screen_height)
        self.planner = DesktopActionPlanner()
        self.executor = DesktopActionExecutor(self.perception, custom_dispatcher)
        self.verifier = DesktopExecutionVerifier()

    def run_goal(self, goal: str, active_window_title: str = "") -> AgentRunReport:
        # 1. Safety check
        check = self.safety_guard.validate_action(
            action_type="autonomous_task",
            target_description=goal,
            window_title=active_window_title,
        )
        if not check.allowed:
            return AgentRunReport(
                goal=goal,
                steps_executed=0,
                success=False,
                message=f"Safety guard veto: {check.reason}",
                details=[],
            )

        # 2. Plan discrete steps
        steps = self.planner.plan_steps_for_intent(goal)
        executed_results: List[ExecutionResult] = []

        # 3. Execute step by step with verification
        for step in steps:
            # Re-check safety per step
            step_check = self.safety_guard.validate_action(
                action_type=step.primitive.value,
                target_description=step.description or step.text_payload or step.target_label,
                window_title=active_window_title,
            )
            if not step_check.allowed:
                return AgentRunReport(
                    goal=goal,
                    steps_executed=len(executed_results),
                    success=False,
                    message=f"Step {step.step_id} blocked: {step_check.reason}",
                    details=executed_results,
                )

            res = self.executor.execute_step(step)
            executed_results.append(res)
            if not res.success:
                return AgentRunReport(
                    goal=goal,
                    steps_executed=len(executed_results),
                    success=False,
                    message=f"Step {step.step_id} failed: {res.details}",
                    details=executed_results,
                )

        return AgentRunReport(
            goal=goal,
            steps_executed=len(executed_results),
            success=True,
            message="Goal executed successfully",
            details=executed_results,
        )
