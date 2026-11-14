"""
mjx.emotions.conversation_dynamics — Conversational Flow, Cadence, and Turn-Taking.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class ConversationalTurn:
    speaker: str           # "user" or "assistant"
    word_count: int
    duration_secs: float
    timestamp: float = field(default_factory=time.time)


class ConversationDynamicsTracker:
    """Monitors rhythm, pace, and pause lengths to optimize interruption sensitivity and timing."""

    def __init__(self, history_window: int = 10):
        self.history_window = history_window
        self.turns: List[ConversationalTurn] = []

    def record_turn(self, speaker: str, text: str, duration_secs: float = 1.0) -> None:
        words = len(text.split()) if text else 0
        turn = ConversationalTurn(
            speaker=speaker,
            word_count=words,
            duration_secs=max(0.1, duration_secs),
            timestamp=time.time(),
        )
        self.turns.append(turn)
        if len(self.turns) > self.history_window:
            self.turns.pop(0)

    def get_average_user_wpm(self) -> float:
        user_turns = [t for t in self.turns if t.speaker == "user"]
        if not user_turns:
            return 130.0  # standard baseline conversational words-per-minute
        total_words = sum(t.word_count for t in user_turns)
        total_mins = sum(t.duration_secs for t in user_turns) / 60.0
        if total_mins <= 0:
            return 130.0
        return round(total_words / total_mins, 1)

    def is_fast_paced(self) -> bool:
        return self.get_average_user_wpm() > 160.0

    def recommend_interruption_sensitivity(self) -> float:
        """Returns 0.0 (high resistance to interruption) to 1.0 (very sensitive to quick interruption)."""
        wpm = self.get_average_user_wpm()
        if wpm > 170.0:
            # Fast, excited speaker -> higher sensitivity to user breaking in
            return 0.85
        if wpm < 100.0:
            # Deliberate, thoughtful speaker -> don't jump in prematurely
            return 0.50
        return 0.65
