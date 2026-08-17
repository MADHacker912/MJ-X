"""Thread-safe orchestration API for MJ's simulated Emotion Engine."""

from __future__ import annotations

from collections import deque
import threading
from typing import Any, Iterable

from .avatar import get_avatar_animation
from .detection import DetectionResult, ai_classifier_prompt, calculate_intensity, detect_fallback, parse_ai_result
from .memory import EmotionMemory
from .state import EmotionState, SUPPORTED_EMOTIONS
from .transitions import decay, transition
from .voice import get_voice_settings


DEFAULT_SETTINGS: dict[str, Any] = {
    "emotion_engine_enabled": True,
    "avatar_emotions_enabled": True,
    "voice_emotions_enabled": True,
    "emotion_intensity": 0.8,
    "emoji_frequency": "low",
    "emotion_decay_time": 180,
    "allow_emotion_memory": True,
}

_STYLE = {
    "neutral": "Natural, direct, and balanced.",
    "happy": "Cheerful wording with light energy; at most one suitable emoji.",
    "excited": "Energetic and concise without shouting or excessive punctuation.",
    "laughing": "A brief natural laugh is okay; do not keep repeating it.",
    "sad": "Use softer wording and calm support; do not dramatise.",
    "crying": "Use only as restrained fictional expression; for real hardship switch to calm caring support.",
    "confused": "Say which part is unclear and ask one precise clarifying question.",
    "surprised": "Acknowledge the unexpected detail briefly, then stay useful.",
    "worried": "Prioritise the urgent facts and safe next action in a concerned, steady tone.",
    "angry": "Use firm controlled frustration only; never insult, threaten, or abuse.",
    "annoyed": "Acknowledge repetition without blaming the user; stay patient and solution-focused.",
    "embarrassed": "Keep the response gentle and low-key; do not tease the user.",
    "shy": "Use warm, understated wording without pretending to have human feelings.",
    "proud": "Recognise the achievement warmly while keeping the praise specific.",
    "curious": "Show engaged curiosity and explore the most relevant detail.",
    "caring": "Use warm supportive language and prioritise the user's wellbeing.",
    "serious": "Be steady, precise, clear, and avoid humour.",
    "sleepy": "Use relaxed, brief wording while remaining accurate.",
    "thinking": "Use a reflective tone; a short 'Hmm, let me think' is acceptable.",
    "scared": "Stay controlled and safety-focused; never amplify fear.",
    "disappointed": "Acknowledge the setback, avoid blame, and focus on recovery steps.",
}


class EmotionEngine:
    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        self.settings = {**DEFAULT_SETTINGS, **(settings or {})}
        self._lock = threading.RLock()
        self._state = EmotionState.neutral()
        self._history: deque[str] = deque(maxlen=12)
        self.memory = EmotionMemory(self.settings["allow_emotion_memory"])

    def calculateEmotionIntensity(self, message: str) -> float:
        return calculate_intensity(message)

    def detectEmotion(
        self,
        message: str,
        conversationHistory: Iterable[Any] | None = None,
        ai_result: str | dict[str, Any] | DetectionResult | None = None,
    ) -> dict[str, Any]:
        if not self.settings["emotion_engine_enabled"]:
            return self.resetEmotion()
        with self._lock:
            history = list(conversationHistory or self._history)
            result = ai_result if isinstance(ai_result, DetectionResult) else parse_ai_result(ai_result) if ai_result else None
            if result is None:
                result = detect_fallback(message, history, self._state.current_emotion)
            scale = max(0.0, min(1.0, float(self.settings["emotion_intensity"])))
            state = self.updateEmotionState(
                result.emotion, result.intensity * scale, result.reason, result.confidence
            )
            self._history.append(message[-1000:])
            self.memory.learn_explicit(message)
            return state

    def previewEmotion(self, message: str, conversationHistory: Iterable[Any] | None = None) -> dict[str, Any]:
        """Update live visuals from an interim transcript without learning or logging it."""
        if not self.settings["emotion_engine_enabled"]:
            return self.getCurrentEmotion()
        with self._lock:
            result = detect_fallback(message, conversationHistory or self._history, self._state.current_emotion)
            return self.updateEmotionState(
                result.emotion,
                result.intensity * float(self.settings["emotion_intensity"]),
                result.reason,
                min(result.confidence, 0.72),
            )

    def updateEmotionState(
        self,
        newEmotion: str,
        intensity: float,
        reason: str = "",
        confidence: float = 0.7,
    ) -> dict[str, Any]:
        with self._lock:
            emotion = newEmotion if newEmotion in SUPPORTED_EMOTIONS else "neutral"
            self._state = transition(
                self._state, emotion, intensity, reason, confidence,
                int(self.settings["emotion_decay_time"]),
            )
            return self.getCurrentEmotion()

    def applyAIResult(self, raw: str | dict[str, Any]) -> dict[str, Any] | None:
        """Refine the current state with validated contextual model output."""
        result = parse_ai_result(raw)
        if result is None:
            return None
        return self.updateEmotionState(
            result.emotion, result.intensity * float(self.settings["emotion_intensity"]),
            result.reason, result.confidence,
        )

    def decayEmotion(self, amount: float = 0.12) -> dict[str, Any]:
        with self._lock:
            self._state = decay(self._state, int(self.settings["emotion_decay_time"]), amount)
            return self.getCurrentEmotion()

    def getEmotionResponseStyle(self) -> dict[str, Any]:
        with self._lock:
            return {
                "emotion": self._state.current_emotion,
                "guidance": _STYLE[self._state.current_emotion],
                "emoji_frequency": self.settings["emoji_frequency"],
                "disclosure": "Simulated response style only; never claim real human feelings.",
            }

    def getAvatarAnimation(self) -> dict[str, Any]:
        with self._lock:
            if not self.settings["avatar_emotions_enabled"]:
                return get_avatar_animation("neutral", 0.0)
            return get_avatar_animation(self._state.current_emotion, self._state.intensity)

    def getVoiceEmotionSettings(self) -> dict[str, Any]:
        with self._lock:
            if not self.settings["voice_emotions_enabled"]:
                return get_voice_settings("neutral", 0.0)
            return get_voice_settings(self._state.current_emotion, self._state.intensity)

    def resetEmotion(self) -> dict[str, Any]:
        with self._lock:
            previous = self._state.current_emotion
            self._state = EmotionState(previous_emotion=previous)
            return self.getCurrentEmotion()

    def getCurrentEmotion(self) -> dict[str, Any]:
        with self._lock:
            return self._state.to_dict()

    def getFrontendPayload(self) -> dict[str, Any]:
        with self._lock:
            voice = self.getVoiceEmotionSettings()
            avatar = self.getAvatarAnimation()
            return {
                "emotion": self._state.current_emotion,
                "intensity": self._state.intensity,
                "animation": avatar["animation"],
                "expression": avatar["expression"],
                "animation_speed": avatar["animation_speed"],
                "blink_animation": avatar["blink_animation"],
                "voice_style": voice["voice_style"],
                "typing_speed": voice["typing_speed"],
                "voice_speed": voice["speed"],
                "voice_volume": voice["volume"],
                "voice_pitch": voice["pitch"],
            }

    def getPromptContext(self) -> str:
        state = self.getCurrentEmotion()
        style = self.getEmotionResponseStyle()
        return (
            "[SIMULATED EMOTION STYLE]\n"
            f"State: {state['current_emotion']} ({state['intensity']:.2f}).\n"
            f"Response guidance: {style['guidance']} Emoji frequency: {style['emoji_frequency']}.\n"
            "This controls presentation only. Never claim real feelings, manipulate the user, or exaggerate serious situations.\n"
        )

    def getAIClassifierPrompt(self, message: str, history: Iterable[Any] | None = None) -> str:
        return ai_classifier_prompt(message, history, self._state.current_emotion)


_default_engine = EmotionEngine()


def detectEmotion(message, conversationHistory=None):
    return _default_engine.detectEmotion(message, conversationHistory)


def calculateEmotionIntensity(message):
    return _default_engine.calculateEmotionIntensity(message)


def updateEmotionState(newEmotion, intensity, reason="", confidence=0.7):
    return _default_engine.updateEmotionState(newEmotion, intensity, reason, confidence)


def decayEmotion():
    return _default_engine.decayEmotion()


def getEmotionResponseStyle():
    return _default_engine.getEmotionResponseStyle()


def getAvatarAnimation():
    return _default_engine.getAvatarAnimation()


def getVoiceEmotionSettings():
    return _default_engine.getVoiceEmotionSettings()


def resetEmotion():
    return _default_engine.resetEmotion()


def getCurrentEmotion():
    return _default_engine.getCurrentEmotion()
