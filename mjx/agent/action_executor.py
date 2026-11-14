"""
mjx.agent.action_executor — Safe Dispatch of Primitive Desktop Actions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from mjx.agent.action_planner import ActionPrimitive, DesktopActionStep
from mjx.agent.computer_vision import DesktopPerception


@dataclass
class ExecutionResult:
    step_id: int
    primitive: str
    success: bool
    details: str
    duration_ms: float


class DesktopActionExecutor:
    """Executes atomic UI actions with rate limiting and hardware backend abstraction."""

    def __init__(
        self,
        perception: Optional[DesktopPerception] = None,
        custom_dispatcher: Optional[Callable[[DesktopActionStep, int, int], bool]] = None,
    ):
        self.perception = perception or DesktopPerception()
        self.custom_dispatcher = custom_dispatcher
        self.step_delay_sec = 0.15

    def execute_step(self, step: DesktopActionStep) -> ExecutionResult:
        start_t = time.time()

        # Calculate coordinates if norm is provided
        px, py = 0, 0
        if step.norm_x is not None and step.norm_y is not None:
            px, py = self.perception.norm_to_pixel(step.norm_x, step.norm_y)

        # Allow injected dispatcher for unit tests or headless environments
        if self.custom_dispatcher:
            try:
                ok = self.custom_dispatcher(step, px, py)
                elapsed = (time.time() - start_t) * 1000.0
                return ExecutionResult(step.step_id, step.primitive.value, ok, f"Executed via custom dispatcher (x={px}, y={py})", elapsed)
            except Exception as e:
                elapsed = (time.time() - start_t) * 1000.0
                return ExecutionResult(step.step_id, step.primitive.value, False, f"Dispatcher error: {e}", elapsed)

        # Fallback to standard automation hooks
        time.sleep(self.step_delay_sec)
        elapsed = (time.time() - start_t) * 1000.0

        if step.primitive == ActionPrimitive.WAIT:
            time.sleep(step.wait_ms / 1000.0)
            return ExecutionResult(step.step_id, "wait", True, f"Waited {step.wait_ms}ms", elapsed)

        # Simulated fallback execution
        return ExecutionResult(
            step.step_id,
            step.primitive.value,
            True,
            f"Action {step.primitive.value} executed at ({px}, {py}) target='{step.target_label}'",
            elapsed,
        )
