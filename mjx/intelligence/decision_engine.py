"""
mjx.intelligence.decision_engine — Action Strategy & Execution Routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .context_engine import WorkingContext
from .intent_classifier import IntentResult, IntentType


class DecisionAction(str, Enum):
    ANSWER_DIRECTLY = "answer_directly"
    EXECUTE_TOOL = "execute_tool"
    EXECUTE_PLAN = "execute_plan"
    SEARCH_MEMORY = "search_memory"
    STORE_MEMORY = "store_memory"
    REQUEST_PERMISSION = "request_permission"
    CLARIFY = "clarify"
    EXPLAIN_UNAVAILABLE = "explain_unavailable"


@dataclass
class DecisionOutcome:
    action: DecisionAction
    target: str
    params: Dict[str, Any]
    reasoning: str
    requires_user_approval: bool = False


class DecisionEngine:
    """Decides the optimal execution path based on context and classified intent."""

    def decide(self, intent: IntentResult, context: WorkingContext) -> DecisionOutcome:
        # 1. Complex Task -> Execute Plan
        if intent.intent_type == IntentType.COMPLEX_TASK or intent.requires_planning:
            return DecisionOutcome(
                action=DecisionAction.EXECUTE_PLAN,
                target="planner",
                params={"prompt": context.user_prompt},
                reasoning="Request requires multi-step decomposition and execution tracking",
            )

        # 2. Memory Store
        if intent.intent_type == IntentType.MEMORY_STORE:
            return DecisionOutcome(
                action=DecisionAction.STORE_MEMORY,
                target="local_memory",
                params={"raw": context.user_prompt},
                reasoning="User explicitly requested storing personal preference or note",
            )

        # 3. Memory Query
        if intent.intent_type == IntentType.MEMORY_QUERY:
            return DecisionOutcome(
                action=DecisionAction.SEARCH_MEMORY,
                target="local_memory",
                params={"query": context.user_prompt},
                reasoning="User queried previous conversation history or stored facts",
            )

        # 4. Tool Action
        if intent.intent_type in (IntentType.TOOL_ACTION, IntentType.SYSTEM_CONTROL):
            tool_name = intent.suggested_action or "generic_tool"
            return DecisionOutcome(
                action=DecisionAction.EXECUTE_TOOL,
                target=tool_name,
                params=intent.detected_entities,
                reasoning=f"User invoked tool action: {tool_name}",
            )

        # 5. Clarification
        if intent.intent_type == IntentType.CLARIFICATION_NEEDED:
            return DecisionOutcome(
                action=DecisionAction.CLARIFY,
                target="user",
                params={},
                reasoning="Request is ambiguous or missing required parameters",
            )

        # 6. Default: Direct Conversational Response
        return DecisionOutcome(
            action=DecisionAction.ANSWER_DIRECTLY,
            target="llm_conversational",
            params={},
            reasoning="Direct contextual conversation",
        )
