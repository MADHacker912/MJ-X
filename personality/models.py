"""Typed contracts for MJ's friend-like personality pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


MODES = (
    "casual_friend", "honest_advisor", "teacher", "supportive", "serious", "debate",
)
AGREEMENT_LEVELS = (
    "agree", "mostly_agree", "partial", "mostly_disagree", "disagree", "uncertain",
)


def clamp(value: Any, default: float = 0.5) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 3)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class ConversationModeResult:
    mode: str = "casual_friend"
    confidence: float = 0.5
    reason: str = "ordinary conversation"

    def __post_init__(self) -> None:
        self.mode = self.mode if self.mode in MODES else "casual_friend"
        self.confidence = clamp(self.confidence)


@dataclass(slots=True)
class ClaimEvaluation:
    agreement_level: str = "uncertain"
    confidence: float = 0.4
    correct_points: list[str] = field(default_factory=list)
    incorrect_points: list[str] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    recommended_response_style: str = "direct_but_friendly"

    def __post_init__(self) -> None:
        if self.agreement_level not in AGREEMENT_LEVELS:
            self.agreement_level = "uncertain"
        self.confidence = clamp(self.confidence, 0.4)


@dataclass(slots=True)
class AdviceAnalysis:
    goal: str = ""
    main_problem: str = ""
    constraints: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    best_option: str = ""
    reason: str = ""
    next_action: str = ""


@dataclass(slots=True)
class SafetyAssessment:
    classification: str = "safe"
    confidence: float = 0.7
    risks: list[str] = field(default_factory=list)
    refusal_needed: bool = False
    safe_alternative: str = ""

    def __post_init__(self) -> None:
        if self.classification not in {"safe", "caution", "high_risk"}:
            self.classification = "safe"
        self.confidence = clamp(self.confidence, 0.7)


@dataclass(slots=True)
class ResponsePlan:
    intent: str = "answer"
    conversation_mode: str = "casual_friend"
    user_emotion: str = "neutral"
    mj_emotion: str = "neutral"
    agreement_level: str = "uncertain"
    main_answer: str = "Answer the main request directly and practically."
    warning_needed: bool = False
    follow_up_needed: bool = False
    memory_to_use: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PersonalityContext:
    mode: ConversationModeResult
    claim: ClaimEvaluation
    advice: AdviceAnalysis
    safety: SafetyAssessment
    plan: ResponsePlan
    response_style: dict[str, Any]
    avatar: dict[str, Any]
    voice: dict[str, Any]
    preferences: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

