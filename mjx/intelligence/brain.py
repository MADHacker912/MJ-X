"""
mjx.intelligence.brain — Central Orchestrator of the MJ-X Intelligence Core.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from mjx.memory import MemoryRepository
from .context_engine import ContextEngine, WorkingContext
from .decision_engine import DecisionAction, DecisionEngine, DecisionOutcome
from .intent_classifier import IntentClassifier, IntentResult
from .planner import TaskPlanner
from .reflection import TaskReflectionEngine
from .response_controller import ResponseController
from .task_manager import TaskManager, TaskPlan


@dataclass
class BrainOutput:
    user_prompt: str
    intent: IntentResult
    decision: DecisionOutcome
    formatted_response: str
    active_plan: Optional[TaskPlan] = None
    requires_approval: bool = False


class IntelligenceBrain:
    """Coordinates intent classification, context assembly, decisions, and planning."""

    def __init__(self, memory_repo: Optional[MemoryRepository] = None):
        self.memory_repo = memory_repo
        self.task_manager = TaskManager()
        self.intent_classifier = IntentClassifier()
        self.context_engine = ContextEngine(memory_repo=self.memory_repo)
        self.decision_engine = DecisionEngine()
        self.planner = TaskPlanner(self.task_manager)
        self.response_controller = ResponseController()
        self.reflection = TaskReflectionEngine()

    def process_message(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        current_emotion: str = "neutral",
        personality_mode: str = "casual_friend",
    ) -> BrainOutput:
        # 1. Intent Classification
        intent = self.intent_classifier.classify(prompt)

        # 2. Context Assembly
        active_plan = None
        plans = self.task_manager.list_active_plans()
        if plans:
            active_plan = plans[0]

        context = self.context_engine.assemble_context(
            user_prompt=prompt,
            conversation_id=conversation_id,
            active_task_dict={"goal": active_plan.goal, "status": active_plan.status.value} if active_plan else None,
            emotion=current_emotion,
            personality_mode=personality_mode,
        )

        # 3. Decision Strategy
        decision = self.decision_engine.decide(intent, context)

        # 4. Action Execution routing
        response_text = ""
        requires_approval = False

        if decision.action == DecisionAction.EXECUTE_PLAN:
            plan = self.planner.plan_request(prompt)
            active_plan = plan
            response_text = f"Maine is task ke liye {len(plan.steps)} steps ka plan banaya hai: '{plan.goal}'."
            if plan.current_step and plan.current_step.requires_approval:
                requires_approval = True

        elif decision.action == DecisionAction.STORE_MEMORY:
            if self.memory_repo:
                self.memory_repo.save_memory("notes", "user_note", prompt, source="brain_direct")
            response_text = "Noted. Maine ise apne local memory me save kar liya hai."

        elif decision.action == DecisionAction.SEARCH_MEMORY:
            if self.memory_repo:
                res = self.memory_repo.search_engine.search_memories(prompt, limit=3)
                if res:
                    items = ", ".join(f"{r['key']}: {r['value']}" for r in res)
                    response_text = f"Local memory ke mutabiq: {items}"
                else:
                    response_text = "Mujhe local memory me isse related koi record nahi mila."
            else:
                response_text = "Memory system local storage me check kiya ja raha hai."

        elif decision.action == DecisionAction.EXECUTE_TOOL:
            response_text = f"Tool invocation queued: {decision.target}."

        else:
            # Conversational response template
            response_text = prompt

        formatted = self.response_controller.format_response(
            response_text,
            confidence=intent.confidence,
            is_hinglish=intent.is_hinglish,
        )

        return BrainOutput(
            user_prompt=prompt,
            intent=intent,
            decision=decision,
            formatted_response=formatted,
            active_plan=active_plan,
            requires_approval=requires_approval,
        )
