# MJ-X SINGULARITY — 03 OMNIBRAIN IMPLEMENTATION

**Subsystem:** Project OMNIBRAIN Cognitive Intelligence Engine  
**Implementation Package:** `mjx/intelligence/`  
**Runtime Integration:** `main.py` (`MJLive._send_user_text`, `MJLive.__init__`)

---

## 1. SUBSYSTEM RESPONSIBILITIES

Project OMNIBRAIN provides the cognitive middleware between incoming raw human utterances (typed text or spoken audio transcripts) and the underlying LLM/tool ecosystem:

1. **Deterministic Intent Classification:** Rapidly determines user intent (conversational, planning, memory search, memory store, tool invocation) without waiting for network LLM completion.
2. **Hinglish/English Dual-Mode Detection:** Automatically identifies colloquial Hindi in Roman script (e.g., "bhai mera calendar check karo", "yeh file delete mat karna") to configure linguistic sensitivity.
3. **Task Planning & Decomposition:** Automatically builds multi-step execution plans (`TaskPlan`) when users issue compound requests.
4. **Context Synthesis:** Gathers relevant working context from conversation history, SQLite memories, and emotional parameters before forming the system prompt.
5. **Response Formatting & Validation:** Formats output strings to match persona expectations and flags tasks requiring explicit user confirmation.

---

## 2. CODE ARTIFACTS & CORE CLASSES

- `mjx/intelligence/brain.py` — `IntelligenceBrain`, `BrainOutput`
- `mjx/intelligence/intent_classifier.py` — `IntentClassifier`, `IntentType`, `IntentResult`
- `mjx/intelligence/context_engine.py` — `ContextEngine`, `WorkingContext`
- `mjx/intelligence/decision_engine.py` — `DecisionEngine`, `DecisionAction`, `DecisionOutcome`
- `mjx/intelligence/planner.py` — `TaskPlanner`, `TaskPlan`, `TaskStep`
- `mjx/intelligence/task_manager.py` — `TaskManager` (state machine for active and completed plans)
- `mjx/intelligence/reflection.py` — `TaskReflectionEngine` (runtime outcome appraisal)
- `mjx/intelligence/response_controller.py` — `ResponseController` (persona-compliant response generation)

---

## 3. INTEGRATION IN LIVE RUNTIME

In `main.py`:
```python
# Initialization in MJLive.__init__
self.brain = IntelligenceBrain(memory_repo=self.memory_repo)

# Execution in MJLive._send_user_text
try:
    brain_out = self.brain.process_message(
        text,
        conversation_id=self._conversation_id,
        current_emotion=self.emotion.getEmotion(),
        personality_mode="casual_friend",
    )
    if brain_out.active_plan:
        plan_desc = f"[ACTIVE TASK PLAN]\nGoal: {brain_out.active_plan.goal}"
        if brain_out.active_plan.current_step:
            plan_desc += f"\nCurrent Step: {brain_out.active_plan.current_step.description}"
        contexts.append(plan_desc)
        self.ui.write_log(f"Plan: {brain_out.active_plan.goal} ({len(brain_out.active_plan.steps)} steps)")
except Exception as exc:
    print(f"[Brain] ⚠️ Processing exception ({exc})")
```

---

## 4. TEST VERIFICATION EVIDENCE

Integrated in `tests/test_singularity_integration.py`:
- `test_brain_initializes_without_memory` — PASSED
- `test_brain_process_simple_conversational` — PASSED
- `test_brain_process_hinglish_detection` — PASSED (Correctly flagged Hinglish inputs)
- `test_brain_process_english_detection` — PASSED (Standard English routing)
- `test_brain_emotion_parameter` — PASSED (Dynamic emotion propagation)
- `test_brain_conversation_id_threading` — PASSED (Conversation session linkage)
- `test_brain_with_memory_repo` — PASSED (Direct SQLite repository integration)
