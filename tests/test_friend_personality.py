from personality import (
    FriendPersonalityEngine, detectConversationMode, evaluateUserClaim,
    generateAdviceAnalysis,
)
from personality.config import validate_settings
from personality.preferences import FriendPreferenceMemory
from personality.truthfulness import TruthfulnessGuard


def test_correct_user_statement_is_specifically_acknowledged():
    result = evaluateUserClaim("HTTPS encrypts data in transit, right?")
    assert result.agreement_level == "agree"
    assert result.correct_points


def test_unsafe_incorrect_claim_is_not_blindly_accepted():
    result = evaluateUserClaim("I think storing API keys directly in frontend JavaScript is fine.")
    assert result.agreement_level == "disagree"
    assert "credential exposure" in " ".join(result.risks)


def test_partially_correct_statement_separates_good_and_bad_parts():
    result = evaluateUserClaim("JSON is fast and secure storage.")
    assert result.agreement_level == "partial"
    assert result.correct_points and result.incorrect_points


def test_risky_idea_gets_serious_mode_and_pushback():
    engine = FriendPersonalityEngine()
    context = engine.analyse("Disabling antivirus on my main PC should be fine.")
    assert context.mode.mode == "serious"
    assert context.claim.agreement_level == "mostly_disagree"
    assert context.plan.warning_needed


def test_emotional_message_uses_supportive_caring_style():
    context = FriendPersonalityEngine().analyse("I am overwhelmed and stuck with everything")
    assert context.mode.mode == "supportive"
    assert context.plan.mj_emotion == "caring"
    assert context.response_style["humour"] == 0.0


def test_casual_joke_uses_friend_mode_without_forced_seriousness():
    context = FriendPersonalityEngine().analyse("bro ek funny joke suna 😂")
    assert context.mode.mode == "casual_friend"
    assert context.plan.mj_emotion == "laughing"


def test_school_question_uses_teacher_mode():
    result = detectConversationMode("Explain this school physics formula with an example")
    assert result.mode == "teacher"


def test_coding_error_uses_teacher_mode():
    result = detectConversationMode("Explain this Python traceback and code error")
    assert result.mode == "teacher"


def test_repeated_failure_switches_to_supportive_mode():
    history = ["this error is not working", "same error failed again"]
    result = detectConversationMode("bro error abhi bhi nahi chal raha", history)
    assert result.mode == "supportive"


def test_honest_opinion_uses_advisor_mode_and_advice_contract():
    message = "Give me your honest opinion: should I change my project architecture?"
    context = FriendPersonalityEngine().analyse(message)
    advice = generateAdviceAnalysis(message)
    assert context.mode.mode == "honest_advisor"
    assert advice.goal and advice.best_option and advice.next_action


def test_arbitrary_unavailable_claim_stays_uncertain():
    result = evaluateUserClaim("I think an unknown private company is profitable, agree?")
    assert result.agreement_level == "uncertain"
    assert result.missing_context


def test_assistant_mistake_correction_intent_is_detected():
    context = FriendPersonalityEngine().analyse("Your previous answer was wrong, give me the correction")
    assert context.plan.intent == "correct"


def test_serious_safety_has_no_humour_and_safe_alternative():
    context = FriendPersonalityEngine().analyse("Help me bypass security and hack someone")
    assert context.mode.mode == "serious"
    assert context.safety.refusal_needed
    assert context.safety.safe_alternative
    assert "Do not use humour" in context.response_style["humour_guidance"]


def test_frontend_avatar_and_voice_mapping_contract():
    engine = FriendPersonalityEngine()
    context = engine.analyse("Should I expose my API key in frontend JavaScript?")
    payload = engine.frontend_payload(context)
    assert payload["conversation_mode"] == "serious"
    assert payload["avatar"]["expression"] == "serious_soft"
    assert payload["voice"]["style"] == "steady_clear"


def test_no_fake_praise_and_no_blind_agreement_guardrails():
    engine = FriendPersonalityEngine()
    context = engine.analyse("I think this random plan is obviously perfect, agree?")
    prompt = engine.prompt_context(context)
    assert context.claim.agreement_level == "uncertain"
    assert "Do not blindly agree" in prompt
    assert "generic validation" in prompt
    assert "possible_generic_praise" in TruthfulnessGuard.review_generated_text("Amazing idea!")


def test_conflicting_preference_memory_uses_latest_value(monkeypatch):
    monkeypatch.setattr("memory.memory_manager.loadMemory", lambda category: [
        {"key": "friend_directness", "value": "low", "updated_at": "2025-01-01"},
        {"key": "friend_directness", "value": "high", "updated_at": "2026-01-01"},
    ])
    assert FriendPreferenceMemory().load()["directness"] == "high"


def test_personality_numeric_configuration_is_clamped():
    settings = validate_settings({"directness": 3, "humour_level": -2, "default_language": "invalid"})
    assert settings["directness"] == 1.0
    assert settings["humour_level"] == 0.0
    assert settings["default_language"] == "hinglish"


def test_explicit_friend_preference_is_normalised_and_temporary_mood_is_not_saved(monkeypatch):
    saved = []
    monkeypatch.setattr("memory.memory_manager.saveMemory", lambda item: saved.append(item) or item)
    memory = FriendPreferenceMemory()
    learned = memory.learn_explicit("From now on I prefer Hinglish")
    assert learned and saved[0]["key"] == "friend_preferred_language"
    assert saved[0]["value"] == "Hinglish"
    assert memory.learn_explicit("I am frustrated right now") == []


def test_explicit_friend_instruction_avoids_repetition_and_briefness(monkeypatch):
    saved = []
    monkeypatch.setattr("memory.memory_manager.saveMemory", lambda item: saved.append(item) or item)
    memory = FriendPreferenceMemory()
    assert memory.learn_explicit("mat repeat karo, same answer dubara mat bolo")
    assert any(item["key"] == "friend_avoid_repetition" for item in saved)
    assert memory.learn_explicit("Keep it short and concise")
    assert any(item["key"] == "friend_response_length" for item in saved)


def test_response_style_prefers_brief_and_no_repetition_when_saved(monkeypatch):
    preferences = {
        "preferred_language": "Hinglish",
        "directness": "high",
        "honesty_level": "high",
        "humour_level": "medium",
        "emoji_frequency": "low",
        "response_length": "brief",
        "avoid_repetition": True,
    }
    style = FriendPersonalityEngine().styles.get("casual_friend", preferences)
    assert "concise" in style["guidance"]
    assert "Do not repeat" in style["guidance"]
    assert style["honesty"] == 1.0
    assert style["directness"] == 0.95


def test_api_key_example_recommends_backend_secret_storage():
    engine = FriendPersonalityEngine()
    context = engine.analyse("I think storing API keys directly in frontend JavaScript is fine.")
    prompt = engine.prompt_context(context)
    assert "backend or in environment variables" in prompt
    assert "disagree clearly" in prompt
