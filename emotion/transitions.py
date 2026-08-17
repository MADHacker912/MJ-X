"""Gradual, safe emotion transitions and time-based decay."""

from __future__ import annotations

from datetime import datetime, timezone

from .state import EmotionState, STRONG_EMOTIONS, iso, utc_now


_FAMILIES = {
    "positive": {"happy", "excited", "laughing", "proud", "curious", "caring"},
    "low": {"sad", "crying", "disappointed", "sleepy", "shy", "embarrassed"},
    "tense": {"worried", "angry", "annoyed", "scared", "serious"},
    "cognitive": {"confused", "thinking", "surprised"},
}


def _family(emotion: str) -> str:
    return next((name for name, values in _FAMILIES.items() if emotion in values), "neutral")


def transition(
    current: EmotionState,
    emotion: str,
    intensity: float,
    reason: str,
    confidence: float,
    decay_seconds: int,
) -> EmotionState:
    intensity = max(0.0, min(1.0, float(intensity)))
    confidence = max(0.0, min(1.0, float(confidence)))
    same = emotion == current.current_emotion
    related = _family(emotion) == _family(current.current_emotion)

    if same:
        blended = current.intensity * 0.55 + intensity * 0.45
    elif related:
        blended = current.intensity * 0.25 + intensity * 0.75
    else:
        # Cross-family changes require stronger evidence, preventing random flips.
        evidence = max(0.35, confidence)
        blended = current.intensity * (1.0 - evidence) + intensity * evidence
        if confidence < 0.48 and current.current_emotion != "neutral":
            emotion = current.current_emotion

    state = EmotionState(
        current_emotion=emotion,
        intensity=blended,
        reason=reason[:240],
        started_at=current.started_at if same else iso(),
        previous_emotion=current.current_emotion if not same else current.previous_emotion,
        confidence=confidence,
    )
    duration = int(decay_seconds * (0.65 if emotion in STRONG_EMOTIONS else 1.0))
    state.set_expiry(duration)
    return state


def decay(state: EmotionState, decay_seconds: int, amount: float = 0.12) -> EmotionState:
    now = utc_now()
    try:
        expired = bool(state.expires_at) and datetime.fromisoformat(state.expires_at) <= now
    except (TypeError, ValueError):
        expired = True
    drop = amount * (1.45 if state.current_emotion in STRONG_EMOTIONS else 1.0)
    intensity = max(0.0, state.intensity - drop)
    if expired or intensity <= 0.16:
        return EmotionState(
            current_emotion="neutral",
            intensity=0.35,
            reason="emotion naturally decayed",
            previous_emotion=state.current_emotion,
            confidence=0.7,
        )
    state.intensity = round(intensity, 3)
    state.confidence = round(max(0.0, state.confidence - 0.04), 3)
    state.set_expiry(decay_seconds)
    return state
