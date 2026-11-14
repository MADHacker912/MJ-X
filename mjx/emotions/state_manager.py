"""
mjx.emotions.state_manager — Emotional State Tracking, Inertia, and Decay.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


VALID_EMOTIONS = {
    "neutral", "happy", "excited", "laughing", "sad", "crying",
    "confused", "surprised", "worried", "angry", "annoyed",
    "embarrassed", "shy", "proud", "curious", "caring",
    "serious", "sleepy", "thinking", "scared", "disappointed",
}


@dataclass
class EmotionalState:
    primary_emotion: str = "neutral"
    intensity: float = 0.5        # 0.0 to 1.0
    confidence: float = 0.8       # 0.0 to 1.0
    valence: float = 0.0          # -1.0 (unpleasant) to +1.0 (pleasant)
    arousal: float = 0.0          # -1.0 (calm) to +1.0 (hyper)
    last_updated: float = field(default_factory=time.time)
    decay_half_life_secs: float = 60.0

    def get_decayed_intensity(self, current_time: Optional[float] = None) -> float:
        now = current_time or time.time()
        elapsed = max(0.0, now - self.last_updated)
        decay_factor = 0.5 ** (elapsed / max(5.0, self.decay_half_life_secs))
        return round(self.intensity * decay_factor, 3)

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        return self.get_decayed_intensity(current_time) < 0.15


class EmotionStateManager:
    """Manages emotional transitions with momentum/inertia to prevent jittery flipping."""

    def __init__(self, inertia: float = 0.35, decay_half_life_secs: float = 60.0):
        self.inertia = max(0.0, min(0.9, inertia))
        self.decay_half_life = decay_half_life_secs
        self.current_state = EmotionalState(decay_half_life_secs=decay_half_life_secs)

    def transition_to(
        self,
        target_emotion: str,
        target_intensity: float = 0.6,
        confidence: float = 0.8,
        valence: float = 0.0,
        arousal: float = 0.0,
        timestamp: Optional[float] = None,
    ) -> EmotionalState:
        now = timestamp or time.time()
        emotion = target_emotion.lower().strip()
        if emotion not in VALID_EMOTIONS:
            emotion = "neutral"

        clamped_target_intensity = max(0.0, min(1.0, target_intensity))
        current_decayed = self.current_state.get_decayed_intensity(now)

        # If transitioning to the same emotion, blend intensities
        if emotion == self.current_state.primary_emotion:
            new_intensity = (self.inertia * current_decayed) + ((1.0 - self.inertia) * clamped_target_intensity)
        else:
            # Different emotion requires overcoming inertia
            if current_decayed > 0.4 and confidence < 0.7:
                # Strong current mood resists low-confidence transient shift
                new_intensity = current_decayed * 0.8
                emotion = self.current_state.primary_emotion
            else:
                new_intensity = clamped_target_intensity

        self.current_state = EmotionalState(
            primary_emotion=emotion,
            intensity=round(new_intensity, 3),
            confidence=round(confidence, 3),
            valence=max(-1.0, min(1.0, valence)),
            arousal=max(-1.0, min(1.0, arousal)),
            last_updated=now,
            decay_half_life_secs=self.decay_half_life,
        )
        return self.current_state

    def tick_decay(self, timestamp: Optional[float] = None) -> EmotionalState:
        now = timestamp or time.time()
        if self.current_state.primary_emotion != "neutral" and self.current_state.is_expired(now):
            self.current_state = EmotionalState(
                primary_emotion="neutral",
                intensity=0.5,
                confidence=1.0,
                valence=0.0,
                arousal=0.0,
                last_updated=now,
                decay_half_life_secs=self.decay_half_life,
            )
        return self.current_state
