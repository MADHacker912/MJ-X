"""
mjx.emotions — Emotion Intelligence & Dynamics Subsystem (Project ECHO).
"""

from mjx.emotions.conversation_dynamics import ConversationDynamicsTracker, ConversationalTurn
from mjx.emotions.emotion_detector import ContextualEmotionDetector, DetectionResult
from mjx.emotions.emotion_engine import IntegratedEmotionEngine
from mjx.emotions.response_style import ResponseStyleAdapter, StyleProfile
from mjx.emotions.state_manager import EmotionalState, EmotionStateManager
from mjx.emotions.voice_expression import VoiceAcoustics, VoiceExpressionController

__all__ = [
    "IntegratedEmotionEngine",
    "EmotionStateManager",
    "EmotionalState",
    "ContextualEmotionDetector",
    "DetectionResult",
    "ResponseStyleAdapter",
    "StyleProfile",
    "VoiceExpressionController",
    "VoiceAcoustics",
    "ConversationDynamicsTracker",
    "ConversationalTurn",
]
