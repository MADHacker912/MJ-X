"""Stable friend-style preference retrieval and explicit learning."""

from __future__ import annotations

import re
from typing import Any


DEFAULT_FRIEND_PREFERENCES: dict[str, Any] = {
    "preferred_language": "Hinglish",
    "honesty_level": "high",
    "humour_level": "medium",
    "directness": "high",
    "emoji_frequency": "low",
    "explanation_style": "simple_and_practical",
    "response_length": "normal",
    "avoid_repetition": False,
    "challenge_user_assumptions": True,
}

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("preferred_language", re.compile(r"\b(?:from now on|remember|i prefer).{0,30}\b(?:hinglish|hindi|english)\b", re.I)),
    ("directness", re.compile(r"\b(?:remember|from now on|i prefer).{0,35}\b(?:direct|blunt|soft|gentle)\b", re.I)),
    ("honesty_level", re.compile(r"\b(?:always|remember|from now on).{0,35}\b(?:honest|truth|agree with me)\b", re.I)),
    ("humour_level", re.compile(r"\b(?:i prefer|from now on|remember).{0,35}\b(?:humou?r|jokes?|funny)\b", re.I)),
    ("emoji_frequency", re.compile(r"\b(?:i prefer|from now on|remember|please).{0,35}\b(?:no|fewer|less|more) emojis?\b", re.I)),
    ("response_length", re.compile(r"\b(?:keep it short|briefly|short answer|short response|short reply|concise(?:ly)?|dont explain too much|don't explain too much|no long explanation|mat itna na bata|mat zyada batao)\b", re.I)),
    ("avoid_repetition", re.compile(r"\b(?:don't repeat|dont repeat|do not repeat|repeat mat karo|mat repeat karo|same answer twice|same thing twice|say the same thing twice|same thing again|no repetition|mat batao|aise mat bolo|aise mat batao|aise mat karo|same answer dubara mat bolo)\b", re.I)),
    ("explanation_style", re.compile(r"\b(?:explain|teach).{0,25}\b(?:simply|step by step|with examples|briefly)\b", re.I)),
    ("challenge_user_assumptions", re.compile(r"\b(?:challenge my assumptions|do not blindly agree|don't blindly agree|correct me when)\b", re.I)),
)
_TRANSIENT_OR_PRIVATE = re.compile(
    r"\b(?:right now|today only|temporarily|password|api key|token|private key|medical record|trauma)\b", re.I
)


class FriendPreferenceMemory:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = bool(enabled)
        self._cache: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        if self._cache is not None:
            return dict(self._cache)
        preferences = dict(DEFAULT_FRIEND_PREFERENCES)
        if not self.enabled:
            return preferences
        try:
            from memory.memory_manager import loadMemory

            records = sorted(
                loadMemory("preferences"), key=lambda item: item.get("updated_at", ""), reverse=True
            )
            seen: set[str] = set()
            for record in records:
                key = str(record.get("key", ""))
                if not key.startswith("friend_"):
                    continue
                pref_key = key.removeprefix("friend_")
                if pref_key in preferences and pref_key not in seen:
                    preferences[pref_key] = record.get("value")
                    seen.add(pref_key)
        except Exception:
            pass
        self._cache = dict(preferences)
        return preferences

    def learn_explicit(self, message: str) -> list[dict[str, Any]]:
        text = " ".join(str(message or "").split())
        if not self.enabled or not text or _TRANSIENT_OR_PRIVATE.search(text):
            return []
        for key, pattern in _PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            value = self._normalise_value(key, match.group(0))
            try:
                from memory.memory_manager import saveMemory

                learned = saveMemory({
                    "category": "preferences",
                    "key": f"friend_{key}",
                    "value": value,
                    "confidence": 0.92,
                    "importance": 8,
                    "source": "explicit_friend_preference",
                })
                self._cache = None
                return [learned]
            except Exception:
                return []
        return []

    @staticmethod
    def _normalise_value(key: str, matched: str) -> Any:
        lower = matched.casefold()
        if key == "preferred_language":
            return next((name for name in ("Hinglish", "Hindi", "English") if name.casefold() in lower), "Hinglish")
        if key == "challenge_user_assumptions":
            return True
        if key == "directness":
            if any(word in lower for word in ("soft", "gentle", "calm")):
                return "gentle"
            if any(word in lower for word in ("high", "direct", "blunt")):
                return "high"
            return "high"
        if key == "honesty_level":
            return "high"
        if key == "emoji_frequency":
            return "high" if "more" in lower else "none" if "no emoji" in lower else "low"
        if key == "response_length":
            if any(word in lower for word in ("short", "brief", "concise", "mat itna", "mat zyada")):
                return "brief"
            if any(word in lower for word in ("detailed", "long", "thorough")):
                return "detailed"
            return "normal"
        if key == "avoid_repetition":
            return True
        if key == "explanation_style":
            if "step by step" in lower:
                return "step_by_step"
            if "example" in lower:
                return "simple_with_examples"
            if any(word in lower for word in ("brief", "short", "concise")):
                return "brief"
            return "simple_and_practical"
        if key == "humour_level":
            return "medium"
        return matched.strip(" .!?")[:220]
