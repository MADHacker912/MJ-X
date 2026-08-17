"""Public API for MJ's simulated Emotion Engine."""

from .engine import (
    DEFAULT_SETTINGS,
    EmotionEngine,
    calculateEmotionIntensity,
    decayEmotion,
    detectEmotion,
    getAvatarAnimation,
    getCurrentEmotion,
    getEmotionResponseStyle,
    getVoiceEmotionSettings,
    resetEmotion,
    updateEmotionState,
)
from .state import EmotionState, SUPPORTED_EMOTIONS

__all__ = [
    "DEFAULT_SETTINGS", "EmotionEngine", "EmotionState", "SUPPORTED_EMOTIONS",
    "detectEmotion", "calculateEmotionIntensity", "updateEmotionState",
    "decayEmotion", "getEmotionResponseStyle", "getAvatarAnimation",
    "getVoiceEmotionSettings", "resetEmotion", "getCurrentEmotion",
]
