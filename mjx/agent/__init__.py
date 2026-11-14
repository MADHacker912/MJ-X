"""
mjx.agent — Autonomous Desktop Agent Subsystem (Project GHOST).
"""

from mjx.agent.action_executor import DesktopActionExecutor, ExecutionResult
from mjx.agent.action_planner import ActionPrimitive, DesktopActionPlanner, DesktopActionStep
from mjx.agent.agent_controller import AgentRunReport, DesktopAgentController
from mjx.agent.computer_vision import DesktopPerception, UIElementBox
from mjx.agent.execution_verifier import DesktopExecutionVerifier, VerificationOutcome
from mjx.agent.safety_guard import AgentSafetyGuard, SafetyCheckResult

__all__ = [
    "DesktopAgentController",
    "AgentRunReport",
    "AgentSafetyGuard",
    "SafetyCheckResult",
    "DesktopPerception",
    "UIElementBox",
    "DesktopActionPlanner",
    "DesktopActionStep",
    "ActionPrimitive",
    "DesktopActionExecutor",
    "ExecutionResult",
    "DesktopExecutionVerifier",
    "VerificationOutcome",
]
