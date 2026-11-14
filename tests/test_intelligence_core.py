"""
Unit tests for mjx.intelligence — The Intelligence Core for MJ-X.
"""

import pytest
from mjx.memory import DatabaseManager, MemoryRepository
from mjx.intelligence import (
    IntelligenceBrain,
    IntentClassifier,
    IntentType,
    TaskManager,
    TaskPlanner,
    TaskStatus,
    ContextEngine,
    DecisionEngine,
    DecisionAction,
    BoundedReasoningLoop,
    ResponseController,
    TaskReflectionEngine,
    FailureType,
)


@pytest.fixture
def repo(tmp_path):
    db_mgr = DatabaseManager(tmp_path / "brain_test.db")
    return MemoryRepository(db_mgr)


def test_intent_classifier():
    classifier = IntentClassifier()

    # Conversational
    r1 = classifier.classify("Hello MJ, how are you doing today?")
    assert r1.intent_type == IntentType.CONVERSATIONAL
    assert r1.is_hinglish is False

    # Hinglish Memory Store
    r2 = classifier.classify("Yaad rakhna mera favorite editor VSCode hai")
    assert r2.intent_type == IntentType.MEMORY_STORE
    assert r2.is_hinglish is True

    # Complex multi-step task
    r3 = classifier.classify("Search for python news and then open terminal")
    assert r3.intent_type == IntentType.COMPLEX_TASK
    assert r3.requires_planning is True


def test_task_manager_and_planner():
    tm = TaskManager()
    planner = TaskPlanner(tm)

    plan = planner.plan_request("Search weather in Delhi and then take a screenshot")
    assert plan.goal.startswith("Search weather")
    assert len(plan.steps) == 2
    assert plan.steps[0].action == "web_search"
    assert plan.steps[1].action == "screen_capture"
    assert plan.steps[1].requires_approval is True

    # Advance step 1
    tm.advance_step(plan.task_id, step_result="Weather is 25C", success=True)
    assert plan.current_step_index == 1
    assert plan.status == TaskStatus.PENDING

    # Advance step 2
    tm.advance_step(plan.task_id, step_result="Screenshot captured", success=True)
    assert plan.status == TaskStatus.COMPLETED

    # Pause and resume
    plan2 = tm.create_plan("Test Plan", [{"action": "a1"}])
    assert tm.pause_plan(plan2.task_id) is True
    assert plan2.status == TaskStatus.PAUSED
    assert tm.resume_plan(plan2.task_id) is True
    assert plan2.status == TaskStatus.RUNNING

    # Cancel
    assert tm.cancel_plan(plan2.task_id) is True
    assert plan2.status == TaskStatus.CANCELLED


def test_context_engine_aggregation(repo):
    repo.save_memory("preferences", "fav_drink", "Chai with ginger")
    ce = ContextEngine(memory_repo=repo)

    ctx = ce.assemble_context(user_prompt="I want my favorite drink", emotion="happy")
    assert ctx.current_emotion == "happy"
    assert len(ctx.relevant_memories) >= 1
    formatted = ctx.format_context_prompt()
    assert "fav_drink" in formatted


def test_decision_engine_routing():
    de = DecisionEngine()
    classifier = IntentClassifier()
    ce = ContextEngine()

    intent_complex = classifier.classify("First clone repository and then run tests")
    context = ce.assemble_context(intent_complex.detected_entities.get("raw_query", ""))
    outcome = de.decide(intent_complex, context)
    assert outcome.action == DecisionAction.EXECUTE_PLAN


def test_bounded_reasoning_loop():
    loop = BoundedReasoningLoop(max_steps=3)

    # Simulated evaluator that terminates at step 2
    def mock_evaluator(step_num, prev_obs):
        if step_num == 2:
            return ("Found solution", "finalize", "Success output", True)
        return (f"Step {step_num} thought", "probe", "Intermediate observation", False)

    trace = loop.execute_loop("Test goal", mock_evaluator)
    assert trace.completed is True
    assert trace.iterations_used == 2
    assert trace.final_result == "Success output"


def test_response_controller_uncertainty():
    rc = ResponseController()
    # High confidence -> no uncertainty prefix
    resp_high = rc.format_response("The capital is Delhi", confidence=0.9)
    assert not resp_high.startswith("I'm not completely certain")

    # Low confidence -> uncertainty prefix added
    resp_low = rc.format_response("The meeting might be at 5pm", confidence=0.4, is_hinglish=False)
    assert "not completely certain" in resp_low


def test_reflection_failure_classification():
    refl = TaskReflectionEngine()

    # Success
    rep1 = refl.evaluate("Open Chrome", "open_app", 0, "Launched", "")
    assert rep1.success is True
    assert rep1.failure_type == FailureType.NONE

    # Permission denied
    rep2 = refl.evaluate("Take shot", "screenshot", 1, "", "Permission denied by security policy")
    assert rep2.success is False
    assert rep2.failure_type == FailureType.PERMISSION_DENIED

    # Timeout
    rep3 = refl.evaluate("Long script", "safe_run", 1, "", "Process timed out after 15s")
    assert rep3.success is False
    assert rep3.failure_type == FailureType.TIMEOUT


def test_intelligence_brain_end_to_end(repo):
    brain = IntelligenceBrain(memory_repo=repo)

    out = brain.process_message("Yaad rakhna mera favorite color royal navy hai")
    assert out.intent.intent_type == IntentType.MEMORY_STORE
    assert "Noted" in out.formatted_response

    # Verify stored in SQLite repository
    mems = repo.list_memories()
    assert len(mems) >= 1
