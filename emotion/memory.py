"""Privacy-safe learning of explicit, stable emotional response preferences."""

from __future__ import annotations

import re
from typing import Any


_PREFERENCE_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("emotion_emoji_frequency", re.compile(r"\b(?:i prefer|from now on|always|remember|please)\b.*\b(no|fewer|less|more) emojis?\b", re.I), "emoji preference"),
    ("emotion_serious_reply_topics", re.compile(r"\b(?:i prefer|from now on|always|remember)\b.*\bserious repl(?:y|ies)\b", re.I), "serious reply preference"),
    ("emotion_humour_style", re.compile(r"\b(?:my|i prefer|remember).{0,30}\b(?:humou?r|jokes?|funny)\b", re.I), "humour preference"),
    ("emotion_disliked_topics", re.compile(r"\b(?:remember|from now on|i dislike|i hate|never joke about)\b.{1,120}", re.I), "explicit topic dislike"),
    ("emotion_positive_topics", re.compile(r"\b(?:remember|my favou?rite|i love|makes? me happy)\b.{1,120}", re.I), "explicit positive topic"),
)

_PRIVATE_OR_TRANSIENT = re.compile(
    r"\b(?:right now|today only|abhi|currently|password|api key|otp|medical record|trauma|"
    r"suicide|self[- ]?harm|sexual|religion|caste|politic)\b", re.I
)


class EmotionMemory:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = bool(enabled)

    def learn_explicit(self, message: str) -> list[dict[str, Any]]:
        """Store only an explicit durable response preference, never a mood event."""
        text = " ".join(message.strip().split())
        if not self.enabled or not text or _PRIVATE_OR_TRANSIENT.search(text):
            return []
        learned: list[dict[str, Any]] = []
        for key, pattern, label in _PREFERENCE_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            value = match.group(0).strip(" .,!?")[:240]
            try:
                from memory.memory_manager import saveMemory

                learned.append(saveMemory({
                    "category": "preferences",
                    "key": key,
                    "value": value,
                    "confidence": 0.9,
                    "importance": 7,
                    "source": "explicit_emotion_preference",
                }))
            except Exception:
                # Emotion handling must remain available if memory storage is down.
                return learned
            break
        return learned

    def get_preferences(self) -> dict[str, Any]:
        if not self.enabled:
            return {}
        try:
            from memory.memory_manager import searchMemory

            records = searchMemory("emotion", category="preferences", fuzzy=False, limit=20)
            return {
                str(record["key"]): record.get("value")
                for record in records
                if str(record.get("key", "")).startswith("emotion_")
            }
        except Exception:
            return {}

