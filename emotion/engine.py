"""Thread-safe orchestration API for MJ's Emotion Engine with Project ECHO unification."""

from __future__ import annotations

from collections import deque
import threading
from typing import Any, Iterable, Optional

from .avatar import get_avatar_animation
from .detection import DetectionResult, ai_classifier_prompt, calculate_intensity, detect_fallback, parse_ai_result
from .memory import EmotionMemory
from .state import EmotionState, SUPPORTED_EMOTIONS
from .transitions import decay, transition
from .voice import get_voice_settings

from mjx.emotions import (
    IntegratedEmotionEngine,
    EmotionStateManager,
    ContextualEmotionDetector,
    ResponseStyleAdapter,
    VoiceExpressionController,
    ConversationDynamicsTracker,
)


DEFAULT_SETTINGS: dict[str, Any] = {
    "emotion_engine_enabled": True,
    "avatar_emotions_enabled": True,
    "voice_emotions_enabled": True,
    "emotion_intensity": 0.8,
    "emoji_frequency": "low",
    "emotion_decay_time": 180,
    "allow_emotion_memory": True,
    "emotion_inertia": 0.35,
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
    """Unified Emotion Engine combining ECHO dynamics, contextual detection, prosody, and safe adaptation."""

    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        self.settings = {**DEFAULT_SETTINGS, **(settings or {})}
        self._lock = threading.RLock()
        self._state = EmotionState.neutral()
        self._history: deque[str] = deque(maxlen=12)
        self.memory = EmotionMemory(self.settings.get("allow_emotion_memory", True))

        # Integrated ECHO Engine
        self.echo = IntegratedEmotionEngine(
            inertia=float(self.settings.get("emotion_inertia", 0.35)),
            decay_half_life_secs=float(self.settings.get("emotion_decay_time", 60.0)),
            emoji_enabled=(self.settings.get("emoji_frequency") in ("high", "medium")),
        )

    def calculateEmotionIntensity(self, message: str) -> float:
        return calculate_intensity(message)

    def detectEmotion(
        self,
        message: str,
        conversationHistory: Iterable[Any] | None = None,
        ai_result: str | dict[str, Any] | DetectionResult | None = None,
    ) -> dict[str, Any]:
        if not self.settings.get("emotion_engine_enabled", True):
            return self.resetEmotion()

        with self._lock:
            history = list(conversationHistory or self._history)
            result = (
                ai_result
                if isinstance(ai_result, DetectionResult)
                else parse_ai_result(ai_result)
                if ai_result
                else None
            )

            if result is None:
                # Use ECHO Contextual Emotion Detector
                echo_res = self.echo.detector.detect(message, history=history)
                # Map to legacy detection result for compatibility
                result = DetectionResult(
                    emotion=echo_res.emotion,
                    intensity=echo_res.intensity,
                    reason=echo_res.reason,
                    confidence=echo_res.confidence,
                )

            scale = max(0.0, min(1.0, float(self.settings.get("emotion_intensity", 0.8))))
            state = self.updateEmotionState(
                result.emotion,
                result.intensity * scale,
                result.reason,
                result.confidence,
            )

            # Record turn in dynamics tracker
            self.echo.dynamics.record_turn("user", message)
            self._history.append(message[-1000:])
            if self.settings.get("allow_emotion_memory", True):
                self.memory.learn_explicit(message)

            return state

    def previewEmotion(self, message: str, conversationHistory: Iterable[Any] | None = None) -> dict[str, Any]:
        """Update live visuals from an interim transcript without learning or logging it."""
        if not self.settings.get("emotion_engine_enabled", True):
            return self.getCurrentEmotion()

        with self._lock:
            echo_res = self.echo.detector.detect(message, history=list(conversationHistory or self._history))
            scale = max(0.0, min(1.0, float(self.settings.get("emotion_intensity", 0.8))))
            return self.updateEmotionState(
                echo_res.emotion,
                echo_res.intensity * scale,
                echo_res.reason,
                min(echo_res.confidence, 0.72),
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

            # Transition via ECHO State Manager (inertia + decay tracking)
            self.echo.state_manager.transition_to(
                target_emotion=emotion,
                target_intensity=intensity,
                confidence=confidence,
            )

            # Sync legacy EmotionState representation
            self._state = transition(
                self._state,
                emotion,
                intensity,
                reason,
                confidence,
                int(self.settings.get("emotion_decay_time", 180)),
            )
            return self.getCurrentEmotion()

    def applyAIResult(self, raw: str | dict[str, Any]) -> dict[str, Any] | None:
        """Refine the current state with validated contextual model output."""
        result = parse_ai_result(raw)
        if result is None:
            return None
        return self.updateEmotionState(
            result.emotion,
            result.intensity * float(self.settings.get("emotion_intensity", 0.8)),
            result.reason,
            result.confidence,
        )

    def decayEmotion(self, amount: float = 0.12) -> dict[str, Any]:
        with self._lock:
            # Tick ECHO decay
            decayed = self.echo.state_manager.tick_decay()
            if decayed.primary_emotion == "neutral":
                self._state = EmotionState.neutral()
            else:
                self._state = decay(self._state, int(self.settings.get("emotion_decay_time", 180)), amount)
            return self.getCurrentEmotion()

    def getEmotionResponseStyle(self) -> dict[str, Any]:
        with self._lock:
            emotion = self._state.current_emotion
            style_prof = self.echo.style_adapter.get_style_profile(emotion)
            return {
                "emotion": emotion,
                "guidance": _STYLE.get(emotion, _STYLE["neutral"]),
                "emoji_frequency": self.settings.get("emoji_frequency", "low"),
                "formality": style_prof.formality,
                "pace": style_prof.pace,
                "disclosure": "Simulated response style only; never claim real human feelings.",
            }

    def getAvatarAnimation(self) -> dict[str, Any]:
        with self._lock:
            if not self.settings.get("avatar_emotions_enabled", True):
                return get_avatar_animation("neutral", 0.0)
            return get_avatar_animation(self._state.current_emotion, self._state.intensity)

    def getVoiceEmotionSettings(self) -> dict[str, Any]:
        with self._lock:
            if not self.settings.get("voice_emotions_enabled", True):
                return {
                    "voice_style": "balanced",
                    "speed": 1.0,
                    "volume": 1.0,
                    "pitch": 1.0,
                    "pause_ms": 300,
                    "typing_speed": "medium",
                }
            return get_voice_settings(self._state.current_emotion, self._state.intensity)

    def resetEmotion(self) -> dict[str, Any]:
        with self._lock:
            previous = self._state.current_emotion
            self._state = EmotionState(previous_emotion=previous)
            self.echo.state_manager.current_state = self.echo.state_manager.transition_to("neutral", 0.5, 1.0)
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

    def getPromptContext(self, message: str = "") -> str:
        state = self.getCurrentEmotion()
        interaction_style = self.echo.style_adapter.detect_interaction_style(message, list(self._history))
        return self.echo.style_adapter.get_prompt_guidance(
            emotion=state["current_emotion"],
            interaction_style=interaction_style,
            intensity=state["intensity"],
        )

    def get_interruption_sensitivity(self) -> float:
        """Returns dynamic interruption sensitivity recommended by conversation dynamics."""
        return self.echo.dynamics.recommend_interruption_sensitivity()

    def record_turn(self, speaker: str, text: str, duration_secs: float = 1.0) -> None:
        """Records conversational turn in ECHO dynamics."""
        self.echo.dynamics.record_turn(speaker, text, duration_secs)

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
