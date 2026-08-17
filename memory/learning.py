"""Conservative rule-based extraction of durable facts from user messages."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import normalize_key


_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|namaste|thanks|thank you|bye)[!. ]*$",
    re.IGNORECASE,
)
_TEMPORARY_RE = re.compile(
    r"\b(now|right now|today only|for now|this minute|temporarily)\b", re.IGNORECASE
)


@dataclass(slots=True)
class LearnedMemory:
    category: str
    key: str
    value: str
    confidence: float
    importance: int
    source: str = "automatic_learning"


class ConversationLearner:
    """Extracts only explicit, durable user statements; it never stores raw chat."""

    _patterns = (
        (re.compile(r"\b(?:remember(?: that)?|don['’]t forget(?: that)?)\s+(.+)", re.I), "notes", 0.88, 7),
        (re.compile(r"\bfrom now on[, ]+(.+)", re.I), "habits", 0.88, 8),
        (re.compile(r"\bmy favou?rite\s+([\w ]+?)\s+(?:is|are)\s+(.+)", re.I), "preferences", 0.94, 7),
        (re.compile(r"\bi prefer\s+(.+?)(?:\s+over\s+(.+))?[.!]?$", re.I), "preferences", 0.9, 7),
        (re.compile(r"\bi always\s+(.+)", re.I), "habits", 0.82, 6),
        (re.compile(r"\bi never\s+(.+)", re.I), "preferences", 0.82, 7),
        (re.compile(r"^always\s+(.+)", re.I), "preferences", 0.86, 8),
        (re.compile(r"^never\s+(.+)", re.I), "preferences", 0.86, 8),
        (re.compile(r"\b(?:don't|dont|mat|na)\s+(?:show|tell|say|use|include|mention)\s+(.+?)(?:[.!?]|$)", re.I), "preferences", 0.92, 8),
        (re.compile(r"\b(?:aise mat karo|aise mat bol|aise mat bata|aise mat samjhao|aise mat likho)(?:[.!?]|$)", re.I), "preferences", 0.9, 8),
        (re.compile(r"\b(?:aise karo|aise batao|aise samjhao|aise hi samjhao|aise hi batao)(?:[.!?]|$)", re.I), "preferences", 0.88, 8),
        (re.compile(r"\bmy name is\s+(.+)", re.I), "identity", 0.98, 10),
        (re.compile(r"\bi live in\s+(.+)", re.I), "locations", 0.92, 8),
        (re.compile(r"\bi work (?:at|for|as)\s+(.+)", re.I), "work", 0.9, 8),
        (re.compile(r"\bi(?:'m| am) (?:working on|building)\s+(.+)", re.I), "projects", 0.88, 8),
        (re.compile(r"\bmy goal is(?: to)?\s+(.+)", re.I), "goals", 0.9, 9),
    )

    def extract(self, text: str) -> list[LearnedMemory]:
        text = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(text) < 5 or len(text) > 1000 or _GREETING_RE.match(text):
            return []
        if _TEMPORARY_RE.search(text) and not re.search(r"\bremember|don't forget\b", text, re.I):
            return []

        learned: list[LearnedMemory] = []
        for pattern, category, confidence, importance in self._patterns:
            match = pattern.search(text)
            if not match:
                continue
            groups = [re.sub(r"[.!?]+$", "", g.strip()) for g in match.groups() if g]
            if not groups:
                continue
            if category == "identity":
                key, value = "name", groups[-1]
            elif category == "locations":
                key, value = "home", groups[-1]
            elif category in {"projects", "goals", "work"}:
                value = groups[-1]
                key = normalize_key(value)[:60]
            elif len(groups) > 1 and category == "preferences":
                key, value = groups[0], groups[-1]
            else:
                value = groups[-1]
                key = normalize_key(value)[:60]
            if len(value) >= 2:
                learned.append(LearnedMemory(category, normalize_key(key), value, confidence, importance))
            break
        return learned
