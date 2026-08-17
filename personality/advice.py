"""Internal decision framing for advice-related conversations."""

from __future__ import annotations

import re
from typing import Any

from .models import AdviceAnalysis
from .safety import assess_safety


def generate_advice_analysis(message: str, context: dict[str, Any] | None = None) -> AdviceAnalysis:
    text = " ".join(str(message or "").split())
    safety = assess_safety(text)
    goal_match = re.search(r"\b(?:i want to|i need to|mera goal|should i)\s+(.+)", text, re.I)
    goal = (goal_match.group(1) if goal_match else text)[:180]
    constraints: list[str] = []
    if re.search(r"\b(?:budget|cheap|money|cost)\b", text, re.I):
        constraints.append("budget")
    if re.search(r"\b(?:urgent|today|deadline|jaldi)\b", text, re.I):
        constraints.append("time")
    if re.search(r"\b(?:beginner|new to|first time)\b", text, re.I):
        constraints.append("current experience")
    return AdviceAnalysis(
        goal=goal,
        main_problem="Choose a practical option without ignoring constraints or downside.",
        constraints=constraints,
        risks=list(safety.risks),
        options=["Keep the current approach and reduce its main risk", "Use a safer or simpler alternative"],
        best_option="Prefer the option that is reversible, evidence-based, and fits the stated constraints.",
        reason="It limits avoidable downside while still moving the user's goal forward.",
        next_action="Confirm the most important missing constraint, or take the smallest reversible step.",
    )


def generateAdviceAnalysis(message, context=None):
    return generate_advice_analysis(message, context)

