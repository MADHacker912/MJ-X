"""
mjx.emotions.emotion_engine — Unified Emotion Engine Facade for MJ-X.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mjx.emotions.conversation_dynamics import ConversationDynamicsTracker
from mjx.emotions.emotion_detector import ContextualEmotionDetector, DetectionResult
from mjx.emotions.response_style import ResponseStyleAdapter
from mjx.emotions.state_manager import EmotionStateManager, EmotionalState
from mjx.emotions.voice_expression import VoiceAcoustics, VoiceExpressionController


class IntegratedEmotionEngine:
    """Master controller managing emotional comprehension, state decay, response modulation, and acoustic prosody."""

    def __init__(self, inertia: float = 0.35, decay_half_life_secs: float = 60.0, emoji_enabled: bool = False):
        self.detector = ContextualEmotionDetector()
        self.state_manager = EmotionStateManager(inertia=inertia, decay_half_life_secs=decay_half_life_secs)
        self.style_adapter = ResponseStyleAdapter(emoji_enabled=emoji_enabled)
        self.voice_controller = VoiceExpressionController()
        self.dynamics = ConversationDynamicsTracker()

    def process_incoming_user_message(
        self,
        text: str,
        history: Optional[List[str]] = None,
        duration_secs: float = 1.0,
    ) -> DetectionResult:
        # Record turn dynamics
        self.dynamics.record_turn("user", text, duration_secs)

        # Detect emotion
        detection = self.detector.detect(text, history)

        # Transition state
        self.state_manager.transition_to(
            target_emotion=detection.emotion,
            target_intensity=detection.intensity,
            confidence=detection.confidence,
            valence=detection.valence,
            arousal=detection.arousal,
        )

        return detection

    def prepare_assistant_turn(
        self,
        draft_response: str,
        duration_secs: float = 1.0,
    ) -> Dict[str, Any]:
        current_state = self.state_manager.current_state

        # Modulate text
        styled_text = self.style_adapter.adapt_message(
            draft_response,
            emotion=current_state.primary_emotion,
            intensity=current_state.intensity,
        )

        # Compute voice parameters
        acoustics = self.voice_controller.compute_acoustics(
            emotion=current_state.primary_emotion,
            intensity=current_state.intensity,
        )

        # Record turn
        self.dynamics.record_turn("assistant", styled_text, duration_secs)

        return {
            "text": styled_text,
            "emotion": current_state.primary_emotion,
            "intensity": current_state.intensity,
            "valence": current_state.valence,
            "arousal": current_state.arousal,
            "acoustics": acoustics,
            "interruption_sensitivity": self.dynamics.recommend_interruption_sensitivity(),
        }

    def get_ui_payload(self) -> Dict[str, Any]:
        """Provides frontend payload compatible with PyQt6 UI animation and widgets."""
        state = self.state_manager.current_state
        return {
            "current_emotion": state.primary_emotion,
            "intensity": state.intensity,
            "valence": state.valence,
            "arousal": state.arousal,
            "is_expired": state.is_expired(),
        }
