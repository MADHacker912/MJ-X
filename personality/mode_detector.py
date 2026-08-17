"""Contextual conversation-mode selection with conservative fallbacks."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .models import ConversationModeResult


_SERIOUS = re.compile(r"\b(?:safety|danger|illegal|privacy|security|api key|password|token|hack|harm|suicide|legal|medical|accident|emergency)\b", re.I)
_ADVICE = re.compile(r"\b(?:should i|what should|advice|decision|choose|career|job offer|invest|money|business|project plan|architecture|honest opinion|smart move|better option)\b", re.I)
_TEACH = re.compile(r"\b(?:explain|teach|learn|revision|homework|school|exam|chapter|formula|example|what is|how does|traceback|exception|syntax error|code error)\b", re.I)
_SUPPORT = re.compile(r"\b(?:stressed|overwhelmed|frustrated|disappointed|upset|confused|stuck|can't do|cannot do|give up|tension|pareshan|samajh nahi)\b", re.I)
_DEBATE = re.compile(r"\b(?:debate|argue|counterargument|challenge my|prove me wrong|do you agree|your opinion|change my mind)\b", re.I)
_CASUAL = re.compile(r"\b(?:joke|funny|lol|haha|bro|bhai|meme|chill|kya scene)\b|[😂🤣]", re.I)
_ERROR = re.compile(r"\b(?:error|failed|not working|nahi chal|crash|traceback)\b", re.I)


def _history_text(history: Iterable[Any] | None) -> str:
    values: list[str] = []
    for item in list(history or [])[-8:]:
        values.append(str(item.get("content", item.get("text", ""))) if isinstance(item, dict) else str(item))
    return " ".join(values)


def detect_conversation_mode(
    message: str,
    conversation_history: Iterable[Any] | None = None,
    user_state: dict[str, Any] | None = None,
) -> ConversationModeResult:
    text = str(message or "").strip()
    history = _history_text(conversation_history)
    scores = {mode: 0.05 for mode in ("casual_friend", "honest_advisor", "teacher", "supportive", "serious", "debate")}
    reasons: dict[str, str] = {}

    for mode, pattern, weight, reason in (
        ("serious", _SERIOUS, 0.92, "safety, privacy, or high-impact topic"),
        ("honest_advisor", _ADVICE, 0.76, "user is asking for an important decision or opinion"),
        ("teacher", _TEACH, 0.7, "user wants an explanation or technical learning help"),
        ("supportive", _SUPPORT, 0.76, "user appears frustrated, stressed, or stuck"),
        ("debate", _DEBATE, 0.85, "user wants assumptions challenged or debated"),
        ("casual_friend", _CASUAL, 0.55, "casual language or humour"),
    ):
        if pattern.search(text):
            scores[mode] += weight
            reasons[mode] = reason

    if _ERROR.search(text) and len(_ERROR.findall(history)) >= 2:
        scores["supportive"] += 0.7
        reasons["supportive"] = "the same technical failure appears repeatedly"
    mood = str((user_state or {}).get("current_emotion", ""))
    if mood in {"sad", "worried", "disappointed", "confused", "annoyed"}:
        scores["supportive"] += 0.22
        reasons.setdefault("supportive", "the current user state needs calm practical support")
    if scores["serious"] > 0.9:
        scores["casual_friend"] = 0.0
    mode = max(scores, key=scores.get)
    confidence = min(0.96, 0.46 + scores[mode] * 0.45)
    return ConversationModeResult(mode, confidence, reasons.get(mode, "ordinary conversational context"))


def detectConversationMode(message, conversationHistory=None, userState=None):
    return detect_conversation_mode(message, conversationHistory, userState)
