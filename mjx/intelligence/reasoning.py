"""
mjx.intelligence.reasoning — Bounded Multi-Step Reasoning Orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

MAX_REASONING_STEPS = 5


@dataclass
class ReasoningStep:
    step_num: int
    thought: str
    action_taken: str
    observation: str
    is_terminal: bool = False


@dataclass
class ReasoningTrace:
    goal: str
    steps: List[ReasoningStep]
    final_result: str
    completed: bool
    iterations_used: int


class BoundedReasoningLoop:
    """Executes controlled reasoning and evaluation with strict iteration bounds."""

    def __init__(self, max_steps: int = MAX_REASONING_STEPS):
        self.max_steps = max_steps

    def execute_loop(
        self,
        goal: str,
        step_evaluator: Callable[[int, str], tuple[str, str, str, bool]],
    ) -> ReasoningTrace:
        """
        Executes bounded reasoning cycles.
        step_evaluator(step_num, previous_observation) -> (thought, action, observation, is_terminal)
        """
        steps = []
        last_obs = "Initial state"
        completed = False
        final_result = ""

        for step_idx in range(1, self.max_steps + 1):
            thought, action, obs, is_terminal = step_evaluator(step_idx, last_obs)
            steps.append(
                ReasoningStep(
                    step_num=step_idx,
                    thought=thought,
                    action_taken=action,
                    observation=obs,
                    is_terminal=is_terminal,
                )
            )
            last_obs = obs
            if is_terminal:
                completed = True
                final_result = obs
                break

        if not completed:
            final_result = f"Reasoning loop reached maximum bound ({self.max_steps} steps) and halted safely."

        return ReasoningTrace(
            goal=goal,
            steps=steps,
            final_result=final_result,
            completed=completed,
            iterations_used=len(steps),
        )
