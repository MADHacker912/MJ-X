# MJ-X SINGULARITY — 02 RUNTIME INTEGRATION MATRIX

**Scope:** Cross-subsystem operational matrix showing how runtime events traverse components.

---

## 1. COMPONENT BINDING & LIFECYCLE MATRIX

| Subsystem | Package Path | Instantiation Location | Primary Entry Points | Bound Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| **P0 Security** | `mjx.security` | `main.py`, `actions/` | `is_emergency_stopped()`, `PermissionManager` | Operating System, Process Signals |
| **P1 Cortex** | `mjx.memory`, `memory/` | `memory/memory_manager.py` | `get_repository()`, `searchMemory()` | SQLite3 FTS5, Data Directory |
| **P2 ECHO** | `mjx.emotions`, `emotion/` | `MJLive.__init__` | `detectEmotion()`, `apply_pcm16_settings()` | PyAudio, NumPy, Avatar UI |
| **OMNIBRAIN** | `mjx.intelligence` | `MJLive.__init__` | `brain.process_message()` | MemoryRepository, TaskPlanner |
| **GHOST** | `mjx.agent` | `MJLive.__init__`, `actions/desktop.py` | `controller.run_goal()`, `validate_action()` | PermissionManager, Desktop Perception |
| **NEXUS** | `mjx.skills` | `MJLive.__init__` | `skill_registry.get_skill()`, `execute_skill()` | PermissionManager, Tool Declarations |
| **AURORA** | `mjx.aurora` | `MJLive.__init__`, `dashboard/` | `generate_pairing_code()`, `parse_mobile_telemetry()` | FastAPI, WebSocket Manager |
| **EVOLVE** | `mjx.evolution` | `MJLive.__init__` | `record_sample()`, `get_success_rate()` | Tool Dispatch, Timer Hooks |

---

## 2. EVENT FLOW TRACE: USER TEXT / SPEECH TO ACTION

```
User Input (Audio / Text)
         │
         ▼
[1] main.py: _send_user_text() / audio pipeline
         │
         ├──► [P2 ECHO] detectEmotion() → Emotional inertia calculated (decay 0.35)
         │
         ├──► [OMNIBRAIN] brain.process_message()
         │        ├── Intent classified (Hinglish/English check)
         │        ├── Relevant context retrieved
         │        └── If multi-step: TaskPlanner generates TaskPlan
         │
         ├──► [P1 CORTEX] format_relevant_memory_for_prompt()
         │        └── FTS5 BM25 search across local SQLite database
         │
         ▼
[2] Gemini Live WebSocket Session (send_client_content)
         │
         ▼
[3] Tool Invocation Request (FunctionCall event)
         │
         ├──► Timer initialized (_tool_start_t)
         │
         ├──► Tool Name Dispatch:
         │        ├── "desktop_control" ──► [GHOST] DesktopAgentController.run_goal()
         │        │                              ├── AgentSafetyGuard.validate_action()
         │        │                              ├── If allowed: DesktopActionExecutor
         │        │                              └── Verifier check
         │        ├── "save_memory"     ──► [P1 CORTEX] repo.save_memory()
         │        ├── "set_emotion"     ──► [P2 ECHO] updateEmotionState()
         │        ├── "runtime_metrics" ──► [EVOLVE] metrics.get_success_rate()
         │        ├── "aurora_status"   ──► [AURORA] pairing status inquiry
         │        └── Registered Skill  ──► [NEXUS] skill_executor.execute_skill()
         │
         ├──► Timer finalized (_elapsed_ms recorded)
         │
         └──► [EVOLVE] metrics.record_sample(tool_name, latency, success, error)
         │
         ▼
[4] Tool Response sent to Gemini & User Interface updated
```

---

## 3. VERIFICATION & RECOVERY STATUS

| Pathway | Happy Path Test | Error / Timeout Handling | Security Gate | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Brain Processing** | `test_brain_process_simple_conversational` | Graceful try/catch, fallback to base text | Non-destructive context | ✅ PASS |
| **Agent Desktop Task** | `test_ghost_integrated_in_desktop_action` | Fallback to sandbox code generation | PermissionManager check | ✅ PASS |
| **Skill Execution** | `test_skill_executor_with_permission_manager` | Returns structured `SkillExecutionResult` | PermissionCategory check | ✅ PASS |
| **Device Pairing** | `test_pairing_pin_verification_success` | Expired sessions dropped; wrong PIN rejected | Constant-time HMAC | ✅ PASS |
| **Telemetry Recording** | `test_record_and_success_rate` | Rolling eviction at 500 samples | Memory caps enforced | ✅ PASS |
