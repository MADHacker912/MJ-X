"""Emotion state model and supported emotion vocabulary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


SUPPORTED_EMOTIONS = (
    "neutral", "happy", "excited", "laughing", "sad", "crying",
    "confused", "surprised", "worried", "angry", "annoyed",
    "embarrassed", "shy", "proud", "curious", "caring", "serious",
    "sleepy", "thinking", "scared", "disappointed",
)

STRONG_EMOTIONS = {"excited", "laughing", "crying", "angry", "scared"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utc_now()).isoformat(timespec="seconds")


@dataclass(slots=True)
class EmotionState:
    current_emotion: str = "neutral"
    intensity: float = 0.5
    reason: str = ""
    started_at: str = ""
    expires_at: str = ""
    previous_emotion: str = "neutral"
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.current_emotion not in SUPPORTED_EMOTIONS:
            self.current_emotion = "neutral"
        if self.previous_emotion not in SUPPORTED_EMOTIONS:
            self.previous_emotion = "neutral"
        self.intensity = round(max(0.0, min(1.0, float(self.intensity))), 3)
        self.confidence = round(max(0.0, min(1.0, float(self.confidence))), 3)
        if not self.started_at:
            self.started_at = iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def neutral(cls) -> "EmotionState":
        return cls()

    def set_expiry(self, seconds: int) -> None:
        self.expires_at = iso(utc_now() + timedelta(seconds=max(5, seconds)))

