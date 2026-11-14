"""
mjx.agent.action_planner — Deconstruction of Intent into Primitive Desktop Steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionPrimitive(str, Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    SCROLL = "scroll"
    WAIT = "wait"
    DRAG = "drag"


@dataclass
class DesktopActionStep:
    step_id: int
    primitive: ActionPrimitive
    target_label: str = ""
    norm_x: Optional[int] = None
    norm_y: Optional[int] = None
    text_payload: str = ""
    key_code: str = ""
    scroll_amount: int = 0
    wait_ms: int = 250
    description: str = ""


class DesktopActionPlanner:
    """Plans ordered sequences of GUI actions to accomplish high-level desktop goals."""

    def plan_steps_for_intent(self, intent_text: str) -> List[DesktopActionStep]:
        low = intent_text.lower().strip()
        steps: List[DesktopActionStep] = []

        if "search" in low or "google" in low:
            # Typical search workflow: click address/search bar, type query, hit enter
            query = low.replace("search for", "").replace("search", "").replace("google", "").strip()
            steps.append(DesktopActionStep(
                step_id=1,
                primitive=ActionPrimitive.CLICK,
                target_label="Search or address bar",
                norm_x=500, norm_y=150,
                description="Click address/search input",
            ))
            steps.append(DesktopActionStep(
                step_id=2,
                primitive=ActionPrimitive.TYPE_TEXT,
                text_payload=query,
                description=f"Type query '{query}'",
            ))
            steps.append(DesktopActionStep(
                step_id=3,
                primitive=ActionPrimitive.PRESS_KEY,
                key_code="enter",
                description="Submit search with Enter",
            ))
        elif "click" in low:
            target = low.replace("click", "").replace("on", "").strip()
            steps.append(DesktopActionStep(
                step_id=1,
                primitive=ActionPrimitive.CLICK,
                target_label=target,
                description=f"Click '{target}'",
            ))
        elif "type" in low:
            text = intent_text.split("type", 1)[1].strip()
            steps.append(DesktopActionStep(
                step_id=1,
                primitive=ActionPrimitive.TYPE_TEXT,
                text_payload=text,
                description=f"Type text '{text}'",
            ))
        else:
            # Generic single target invocation
            steps.append(DesktopActionStep(
                step_id=1,
                primitive=ActionPrimitive.CLICK,
                target_label=intent_text,
                description=f"Interact with '{intent_text}'",
            ))

        return steps
