from datetime import datetime, timedelta, timezone

from emotion import EmotionEngine
from emotion.detection import detect_fallback, parse_ai_result
from emotion.state import EmotionState
from emotion.transitions import decay
from emotion.voice import apply_pcm16_settings
from emotion.memory import EmotionMemory
from memory.config_manager import _validate_emotion_settings
import memory.config_manager as config_manager


def test_contextual_detection_examples():
    cases = {
        "bro 😂 ye bohot funny tha": "laughing",
        "I am really worried, urgent error aa raha hai!!!": "worried",
        "I do not understand this part, kya matlab hai??": "confused",
        "I finally passed the exam!": "proud",
        "I am sleepy, bohot neend aa rahi hai": "sleepy",
    }
    for message, expected in cases.items():
        assert detect_fallback(message).emotion == expected


def test_serious_situation_is_not_dramatised():
    result = detect_fallback("My friend died yesterday 😭")
    assert result.emotion in {"caring", "serious", "worried"}
    assert result.intensity <= 0.72


def test_history_can_detect_repeated_error_annoyance():
    history = ["same error again", "the error is still not working"]
    assert detect_fallback("bro baar baar error aa raha hai", history).emotion == "annoyed"


def test_frontend_contract_and_ranges():
    engine = EmotionEngine({"emotion_intensity": 1.0})
    engine.updateEmotionState("happy", 0.8, "good news", 0.9)
    payload = engine.getFrontendPayload()
    assert payload["emotion"] == "happy"
    assert payload["animation"] == "smile_bounce"
    assert payload["voice_style"] == "cheerful"
    assert payload["typing_speed"] == "fast"
    assert 0 <= payload["intensity"] <= 1


def test_malformed_ai_result_is_rejected():
    assert parse_ai_result("not json") is None
    assert parse_ai_result({"emotion": "vengeful", "intensity": 1}) is None
    parsed = parse_ai_result('{"emotion":"curious","intensity":0.7,"confidence":0.8,"reason":"question"}')
    assert parsed and parsed.emotion == "curious"


def test_expired_emotion_returns_to_neutral():
    state = EmotionState(current_emotion="angry", intensity=0.9, confidence=0.9)
    state.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert decay(state, 180).current_emotion == "neutral"


def test_pcm_voice_processing_preserves_pcm_shape():
    original = (b"\x10\x00\xf0\xff") * 100
    styled = apply_pcm16_settings(original, {"speed": 1.0, "volume": 0.9})
    assert styled
    assert len(styled) % 2 == 0


def test_emotion_memory_learns_only_explicit_stable_preferences(monkeypatch):
    saved = []
    monkeypatch.setattr("memory.memory_manager.saveMemory", lambda item: saved.append(item) or item)
    memory = EmotionMemory(enabled=True)
    assert memory.learn_explicit("I prefer fewer emojis in your replies")
    assert saved[0]["key"] == "emotion_emoji_frequency"
    assert memory.learn_explicit("I feel sad right now") == []
    assert memory.learn_explicit("Remember my medical record makes me worried") == []


def test_developer_settings_are_validated():
    settings = _validate_emotion_settings({
        "emotion_intensity": 8,
        "emotion_decay_time": 1,
        "emoji_frequency": "constant",
    })
    assert settings["emotion_intensity"] == 1.0
    assert settings["emotion_decay_time"] == 15
    assert settings["emoji_frequency"] == "low"


def test_voice_interruption_setting_persists_without_losing_config(tmp_path, monkeypatch):
    config_file = tmp_path / "api_keys.json"
    config_file.write_text('{"gemini_api_key":"keep-me"}', encoding="utf-8")
    monkeypatch.setattr(config_manager, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", config_file)
    config_manager.save_voice_interruption_enabled(False)
    assert config_manager.get_voice_interruption_enabled() is False
    assert config_manager.load_api_keys()["gemini_api_key"] == "keep-me"
