"""
tests.test_emotions_ecosystem — Unit tests for mjx.emotions (Project ECHO).
"""

import time
import pytest

from mjx.emotions import (
    IntegratedEmotionEngine,
    EmotionStateManager,
    ContextualEmotionDetector,
    ResponseStyleAdapter,
    VoiceExpressionController,
    ConversationDynamicsTracker,
)


def test_contextual_emotion_detection_hinglish_and_english():
    detector = ContextualEmotionDetector()

    # Happy / laughing
    res1 = detector.detect("bhai ye bohot funny hai 😂")
    assert res1.emotion == "laughing"
    assert res1.intensity >= 0.7

    # Worried
    res2 = detector.detect("urgent error aa raha hai system crash ho gaya")
    assert res2.emotion == "worried"

    # Confused
    res3 = detector.detect("kya matlab hai iska???")
    assert res3.emotion == "confused"

    # Repeated error annoyance in history
    history = ["database error failed", "retry error connection refused"]
    res4 = detector.detect("bro baar baar fail ho raha hai", history=history)
    assert res4.emotion == "annoyed"


def test_emotion_state_manager_inertia_and_decay():
    mgr = EmotionStateManager(inertia=0.4, decay_half_life_secs=10.0)

    # Initial state
    assert mgr.current_state.primary_emotion == "neutral"

    # Transition to happy
    now = time.time()
    st1 = mgr.transition_to("happy", target_intensity=0.8, confidence=0.9, timestamp=now)
    assert st1.primary_emotion == "happy"
    assert st1.intensity == 0.8

    # Simulate time passing for decay (10s = half-life)
    decayed_val = st1.get_decayed_intensity(current_time=now + 10.0)
    assert pytest.approx(decayed_val, abs=0.05) == 0.4

    # Expired check at 40s (4 half lives = 0.8 * 0.0625 = 0.05 < 0.15)
    assert st1.is_expired(current_time=now + 40.0) is True

    # Decay tick resets to neutral
    mgr.tick_decay(timestamp=now + 40.0)
    assert mgr.current_state.primary_emotion == "neutral"


def test_response_style_adaptation():
    adapter = ResponseStyleAdapter(emoji_enabled=False)

    # Sad / Empathetic situation gets empathetic prefix
    styled_sad = adapter.adapt_message("I lost my keys", emotion="sad", intensity=0.8)
    assert "Main samajh sakta hu" in styled_sad

    # Worried gets supportive prefix
    styled_worried = adapter.adapt_message("Server is down", emotion="worried", intensity=0.8)
    assert "Fikar mat kijiye" in styled_worried


def test_voice_expression_acoustics_and_pcm():
    ctrl = VoiceExpressionController()

    acoustics_happy = ctrl.compute_acoustics("happy", intensity=0.9)
    assert acoustics_happy.speed > 1.0
    assert acoustics_happy.volume >= 1.0

    acoustics_sad = ctrl.compute_acoustics("sad", intensity=0.9)
    assert acoustics_sad.speed < 1.0
    assert acoustics_sad.pause_ms > 300

    # Safe PCM gain manipulation
    dummy_pcm = (b"\x10\x00\x20\x00") * 50
    processed = ctrl.process_pcm16_chunk(dummy_pcm, acoustics_happy)
    assert len(processed) == len(dummy_pcm)


def test_conversation_dynamics_tracking():
    tracker = ConversationDynamicsTracker()

    tracker.record_turn("user", "Hello how are you doing today?", duration_secs=2.0)
    # 6 words in 2 seconds = 180 wpm
    assert tracker.is_fast_paced() is True
    assert tracker.recommend_interruption_sensitivity() > 0.7


def test_integrated_emotion_engine_flow():
    engine = IntegratedEmotionEngine()

    # User message
    det = engine.process_incoming_user_message("I cleared my certification exam finally!")
    assert det.emotion == "happy" or det.emotion == "proud"

    # Assistant turn preparation
    res = engine.prepare_assistant_turn("Congratulations! Bohot badhiya!")
    assert res["emotion"] in {"happy", "proud"}
    assert res["acoustics"].speed >= 1.0

    # UI payload check
    ui = engine.get_ui_payload()
    assert "current_emotion" in ui
    assert "intensity" in ui
