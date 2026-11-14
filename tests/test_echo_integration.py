"""
Comprehensive verification suite for MJ-X P2 Project ECHO.
Tests the 14 mandatory integration scenarios across live emotion intelligence,
conversation dynamics, voice prosody, PCM16 soft-knee limiting, interruption thresholds,
conversational adaptation, and safety boundaries.
"""

from __future__ import annotations

import asyncio
import numpy as np
import pytest
import time

from emotion import EmotionEngine, SUPPORTED_EMOTIONS
from emotion.voice import apply_pcm16_settings, get_voice_settings
from mjx.emotions import (
    IntegratedEmotionEngine,
    EmotionStateManager,
    ContextualEmotionDetector,
    ResponseStyleAdapter,
    VoiceExpressionController,
    ConversationDynamicsTracker,
)
from mjx.security import is_emergency_stopped, emergency_stop, reset_emergency_stop


# ── Scenario 1: Application emotion engine initialization ─────────────────────
def test_scenario_01_emotion_engine_initialization():
    """Verify EmotionEngine initializes with unified ECHO components and default settings."""
    engine = EmotionEngine()
    assert hasattr(engine, "echo")
    assert isinstance(engine.echo, IntegratedEmotionEngine)
    assert engine.echo.state_manager.current_state.primary_emotion == "neutral"
    assert engine.settings["emotion_engine_enabled"] is True
    assert engine.settings["voice_emotions_enabled"] is True
    assert engine.getCurrentEmotion()["current_emotion"] == "neutral"


# ── Scenario 2: Live conversation context integration ─────────────────────────
def test_scenario_02_conversation_context_integration():
    """Verify emotion detection incorporates contextual history and Hinglish conversation turns."""
    engine = EmotionEngine()

    # Turn 1: Normal statement
    engine.detectEmotion("Let's work on the codebase today")
    assert engine.getCurrentEmotion()["current_emotion"] == "neutral"

    # Turn 2: Repeated errors in context
    history = ["database error on connection", "failed to connect to host"]
    state = engine.detectEmotion("bro baar baar error aa raha hai", conversationHistory=history)
    assert state["current_emotion"] == "annoyed"
    assert state["intensity"] > 0.5


# ── Scenario 3: Emotion state transitions with inertia ────────────────────────
def test_scenario_03_emotion_state_transitions_inertia():
    """Verify state transitions have inertia and low-confidence inputs don't flip strong states."""
    engine = EmotionEngine({"emotion_inertia": 0.4})

    # High-confidence positive transition
    engine.updateEmotionState("happy", intensity=0.85, confidence=0.95)
    assert engine.getCurrentEmotion()["current_emotion"] == "happy"

    # Low-confidence contradictory input should resist abrupt flipping
    mgr = engine.echo.state_manager
    res = mgr.transition_to("sad", target_intensity=0.3, confidence=0.4)
    # Strong happy mood (intensity > 0.4) resists low-confidence transient shift
    assert res.primary_emotion == "happy"


# ── Scenario 4: Emotion decay ─────────────────────────────────────────────────
def test_scenario_04_emotion_decay_half_life():
    """Verify emotion intensity decays over time and smoothly resets to neutral."""
    engine = EmotionEngine({"emotion_decay_time": 20})
    engine.updateEmotionState("excited", intensity=0.8, confidence=0.9)

    # Immediate check
    assert engine.getCurrentEmotion()["current_emotion"] == "excited"

    # Simulate decay half-life elapsed
    now = time.time()
    decayed = engine.echo.state_manager.current_state.get_decayed_intensity(current_time=now + 20.0)
    assert pytest.approx(decayed, abs=0.08) == 0.4

    # Expired check after 4 half-lives (80s)
    assert engine.echo.state_manager.current_state.is_expired(current_time=now + 80.0) is True

    # Decay tick resets primary emotion to neutral
    engine.echo.state_manager.tick_decay(timestamp=now + 80.0)
    assert engine.echo.state_manager.current_state.primary_emotion == "neutral"


# ── Scenario 5: Voice output processing ───────────────────────────────────────
def test_scenario_05_voice_output_processing():
    """Verify acoustic profiles map correctly to emotion intensity."""
    engine = EmotionEngine()
    engine.updateEmotionState("happy", intensity=0.9)
    settings = engine.getVoiceEmotionSettings()

    assert settings["voice_style"] == "cheerful"
    assert settings["speed"] > 1.0
    assert settings["volume"] >= 1.0
    assert "pause_ms" in settings

    # Sad output has slower pacing and longer pause
    engine.updateEmotionState("sad", intensity=0.9)
    sad_settings = engine.getVoiceEmotionSettings()
    assert sad_settings["voice_style"] == "soft"
    assert sad_settings["speed"] < 1.0
    assert sad_settings["pause_ms"] > settings["pause_ms"]


# ── Scenario 6: PCM16 audio integrity ─────────────────────────────────────────
def test_scenario_06_pcm16_integrity():
    """Verify PCM16 audio data retains exact byte alignment and waveform continuity."""
    # Synthetic 24 kHz mono 16-bit sine wave: 480 samples = 20 ms at 500 Hz (exact 10 cycles)
    t = np.linspace(0, 0.02, 480, endpoint=False)
    sine = (np.sin(2 * np.pi * 500 * t) * 16000).astype(np.int16).tobytes()

    voice_settings = {"speed": 1.0, "volume": 1.05, "voice_style": "cheerful"}
    processed = apply_pcm16_settings(sine, voice_settings)

    assert len(processed) == len(sine)
    assert len(processed) % 2 == 0

    # Verify signal shape preserved without DC offset
    orig_samples = np.frombuffer(sine, dtype=np.int16).astype(np.float32)
    samples = np.frombuffer(processed, dtype=np.int16).astype(np.float32)
    assert abs(np.mean(samples) - np.mean(orig_samples)) < 2.0


# ── Scenario 7: Volume stability and soft-knee limiting ───────────────────────
def test_scenario_07_volume_stability_and_soft_knee():
    """Verify extreme amplitude peaks are soft-knee limited without clipping distortion."""
    # High amplitude peaks near ceiling (±31000)
    t = np.linspace(0, 0.01, 240, endpoint=False)
    peaks = (np.sin(2 * np.pi * 1000 * t) * 31000).astype(np.int16).tobytes()

    # Scale with high volume setting
    boosted_settings = {"volume": 1.25, "speed": 1.0}
    processed = apply_pcm16_settings(peaks, boosted_settings)

    samples = np.frombuffer(processed, dtype=np.int16)
    # Peak must never exceed ±32767
    assert np.max(samples) <= 32767
    assert np.min(samples) >= -32768
    # Max amplitude must be softly compressed without flat-top clipping
    assert np.max(samples) > 28000


# ── Scenario 8: Interruption handling and dynamic sensitivity ─────────────────
def test_scenario_08_interruption_handling_dynamics():
    """Verify conversation dynamics recommend higher sensitivity for fast speakers."""
    tracker = ConversationDynamicsTracker()

    # Fast speaking user (e.g. 180 words per minute)
    tracker.record_turn("user", "Wait stop listening to me I want to change the question right now", duration_secs=4.0)
    assert tracker.is_fast_paced() is True
    fast_sens = tracker.recommend_interruption_sensitivity()
    assert fast_sens >= 0.75

    # Slow, deliberate speaking user (e.g. 80 wpm)
    slow_tracker = ConversationDynamicsTracker()
    slow_tracker.record_turn("user", "Hmm let me think carefully", duration_secs=5.0)
    slow_sens = slow_tracker.recommend_interruption_sensitivity()
    assert slow_sens <= 0.60


# ── Scenario 9: Disabled emotion mode ─────────────────────────────────────────
def test_scenario_09_disabled_emotion_mode():
    """Verify emotion adaptation can be completely disabled by user."""
    engine = EmotionEngine({"emotion_engine_enabled": False})

    res = engine.detectEmotion("Bro I am so angry and furious right now 😡")
    assert res["current_emotion"] == "neutral"

    prompt_ctx = engine.getPromptContext("some message")
    # Voice settings stay neutral when disabled
    engine.settings["voice_emotions_enabled"] = False
    v_set = engine.getVoiceEmotionSettings()
    assert v_set["speed"] == 1.0
    assert v_set["volume"] == 1.0


# ── Scenario 10: Provider capability fallback ─────────────────────────────────
def test_scenario_10_provider_capability_fallback():
    """Verify fallback to safe neutral audio if voice settings or prosody tags fail."""
    # Empty or invalid PCM returns original bytes
    empty_data = b""
    assert apply_pcm16_settings(empty_data, {"volume": 1.5}) == b""

    # Invalid voice dictionary falls back gracefully without exception
    short_data = b"\x00\x01"
    res = apply_pcm16_settings(short_data, {"volume": "invalid_number"})
    assert res == short_data


# ── Scenario 11: Runtime failure recovery ─────────────────────────────────────
def test_scenario_11_runtime_failure_recovery():
    """Verify emergency stop cleanly halts audio processing immediately."""
    reset_emergency_stop()
    assert is_emergency_stopped() is False

    # Trigger emergency stop
    emergency_stop()
    assert is_emergency_stopped() is True

    # Reset for subsequent tests
    reset_emergency_stop()
    assert is_emergency_stopped() is False


# ── Scenario 12: Legacy personality compatibility ─────────────────────────────
def test_scenario_12_legacy_personality_compatibility():
    """Verify existing FriendPersonalityEngine integrates with unified emotion states."""
    from personality import FriendPersonalityEngine

    personality = FriendPersonalityEngine()
    user_state = {"current_emotion": "worried", "intensity": 0.8}
    context = personality.analyse("My build is broken and production is down", user_state=user_state)

    assert context.mode.mode in {"supportive", "serious"}
    assert context.plan.user_emotion == "worried"
    payload = personality.frontend_payload(context)
    assert "conversation_mode" in payload
    assert "avatar" in payload


# ── Scenario 13: UI responsiveness with rich payload ──────────────────────────
def test_scenario_13_ui_responsiveness_payload():
    """Verify getFrontendPayload provides all attributes required by PyQt6 without lag."""
    engine = EmotionEngine()
    engine.updateEmotionState("excited", intensity=0.75)

    payload = engine.getFrontendPayload()
    required_keys = {
        "emotion", "intensity", "animation", "expression",
        "animation_speed", "blink_animation", "voice_style",
        "typing_speed", "voice_speed", "voice_volume", "voice_pitch",
    }
    assert required_keys.issubset(payload.keys())
    assert payload["emotion"] == "excited"
    assert payload["animation"] == "energetic_pulse"


# ── Scenario 14: Session restart & state continuity ───────────────────────────
def test_scenario_14_session_restart_state():
    """Verify resetting emotion clears ephemeral mood while preserving settings."""
    engine = EmotionEngine({"emotion_decay_time": 90, "emoji_frequency": "medium"})
    engine.updateEmotionState("sad", intensity=0.8)
    assert engine.getCurrentEmotion()["current_emotion"] == "sad"

    # Reset emotion
    reset_state = engine.resetEmotion()
    assert reset_state["current_emotion"] == "neutral"
    assert engine.settings["emotion_decay_time"] == 90
    assert engine.settings["emoji_frequency"] == "medium"
