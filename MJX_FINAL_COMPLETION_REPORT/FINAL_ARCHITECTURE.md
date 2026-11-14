# MJ-X SINGULARITY — 01 FINAL ARCHITECTURE

**System:** MJ-X Desktop Multimodal AI Assistant  
**Release Target:** Unified Production Runtime  
**Core Framework:** Python 3.11+, PyQt6, Gemini 2.5 Live Multimodal WebSockets, SQLite3  
**Status:** COMPLETE & VERIFIED (173/173 Tests Passing)

---

## 1. HIGH-LEVEL TOPOLOGY

```
                    ┌──────────────────────────────────────────────┐
                    │               USER INTERFACE                 │
                    │      (PyQt6 Canvas / System Tray / HUD)      │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │            CORE RUNTIME (main.py)            │
                    │               class MJLive                   │
                    └───────┬──────────────┬──────────────┬────────┘
                            │              │              │
         ┌──────────────────┘              │              └──────────────────┐
         ▼                                 ▼                                 ▼
┌─────────────────┐              ┌──────────────────┐              ┌─────────────────┐
│   PERCEPTION    │              │   INTELLIGENCE   │              │   PERSISTENCE   │
│ Screen / Audio  │              │ OMNIBRAIN / ECHO │              │ Cortex (SQLite) │
└────────┬────────┘              └────────┬─────────┘              └────────┬────────┘
         │                                │                                 │
         │         ┌──────────────────────┴──────────────────────┐          │
         │         ▼                                             ▼          │
         │  ┌──────────────┐                             ┌──────────────┐   │
         └─►│  AGENT CORE  │                             │  NEXUS HUB   ├───┘
            │ GHOST Agent  │                             │ Skills / MCP │
            └──────┬───────┘                             └──────┬───────┘
                   │                                            │
                   ▼                                            ▼
            ┌──────────────┐                             ┌──────────────┐
            │ OS ACTIONS   │                             │   AURORA     │
            │ Desktop / App│                             │ Mobile Bridge│
            └──────────────┘                             └──────────────┘
```

---

## 2. SUBSYSTEM INTERACTION & INTEGRATION ARCHITECTURE

### A. Live Audio & Multimodal Pipeline
- **Input:** Microphone captures 16kHz PCM16, buffered into asyncio queue.
- **Dynamic Barge-In:** Real-time RMS speech detection calculated against output speaker feedback via `_barge_in_threshold()`.
- **ECHO Voice Guard:** Output 24kHz PCM stream passes through soft-knee tanh compression, 2.5dB dynamic gain adjustment, and emotional pitch/speed modulation before hitting ALSA/PulseAudio/WASAPI speakers.
- **Vision Feed:** Screen snapshots and camera frames captured on-demand and injected into the active Gemini Live bidirectional WebSocket session.

### B. OMNIBRAIN Cognitive Engine (`mjx/intelligence/`)
- Intercepts all text interactions and multimodal commands.
- Coordinates:
  1. `IntentClassifier`: Rapid regex and semantic pattern categorization with automatic Hinglish / Hindi-Latin detection.
  2. `ContextEngine`: Pulls working state from recent conversational turns and relevant Cortex memories.
  3. `DecisionEngine`: Determines whether to answer directly, plan multi-step execution, query SQLite memory, or trigger system actions.
  4. `TaskPlanner` & `TaskManager`: Constructs discrete execution steps for multi-turn user directives.
  5. `ResponseController`: Formats and personalizes assistant turns while maintaining emotional coherence.

### C. GHOST Autonomous Desktop Agent (`mjx/agent/`)
- Directs desktop automation through `actions/desktop.py` and `actions/computer_control.py`.
- Enforces strict safety boundary through `AgentSafetyGuard`:
  - Validates requested actions against `PermissionManager`.
  - Blocks privileged OS inputs without explicit administrative authorization.
  - Generates discrete action steps (`DesktopActionPlanner`) and verifies visual outcomes (`DesktopExecutionVerifier`).

### D. CORTEX Local-First Memory Subsystem (`memory/`, `mjx/memory/`)
- Unified repository pattern backed by SQLite3 at `data/mjx_memory.db`.
- Canonical schema includes:
  - `memories`: Key-value knowledge graph with categories, confidence, importance scores.
  - `conversations` & `conversation_turns`: Complete turn-level transcripts.
  - `memories_fts`: SQLite FTS5 full-text indexing with BM25 ranking and Hinglish transliteration normalization.
- Zero secondary conflicting JSON stores; legacy endpoints route directly to the SQLite repository.

### E. NEXUS Extensibility & Skills System (`mjx/skills/`)
- Dynamic registry (`SkillRegistry`) supporting runtime registration, trigger phrase search, and lifecycle management.
- Sandboxed execution (`SkillExecutor`) enforcing `PermissionCategory` grants before invoking skill actions.
- Model Context Protocol (`MCPAdapter`) supporting standardized external tool schemas.

### F. AURORA Mobile Companion & Hub Bridge (`mjx/aurora/`, `mjx/hub/`, `dashboard/`)
- Secure pairing using short-lived 6-digit PINs, HMAC constant-time validation, and 48-character hex session tokens.
- Bidirectional telemetry protocol parsing device battery, charging state, Wi-Fi status, and clipboard contents.
- Localhost-bound dashboard server (`127.0.0.1:8000`) protected with AES-256-CBC session-derived encryption.

### G. EVOLVE Performance & Reliability Telemetry (`mjx/evolution/`)
- Non-intrusive operational tracking via `EvolutionMetricsCollector`.
- Records latency, success rates, and failure categories across all tool executions.
- Zero autonomous code self-modification; telemetry is strictly analytical and deterministic.

---

## 3. FILE SYSTEM AND REPOSITORY TOPOLOGY

```
MJ-X/
├── main.py                     # Central PyQt6 & Gemini Live runtime
├── ui.py                       # PyQt6 UI layout, HUD, avatar rendering
├── actions/                    # Built-in tool execution engines
│   ├── desktop.py              # Desktop management & GHOST agent routing
│   ├── file_processor.py       # Permission-gated file inspections
│   ├── open_app.py             # Cross-platform application launcher
│   └── web_search.py           # DuckDuckGo & news query tools
├── core/                       # Core helper processes
│   ├── self_modifier.py        # Locked-down administrative modification
│   ├── sleep_inhibitor.py      # System sleep prevention
│   └── neural_brain.py         # Secondary intelligence routines
├── memory/                     # Cortex memory management interface
│   ├── memory_manager.py       # Unified SQLite repository bridge
│   └── config_manager.py       # User preference persistence
├── emotion/                    # ECHO emotion processing engine
│   ├── engine.py               # Integrated emotion engine bridge
│   ├── voice.py                # Soft-knee PCM limiter & audio modulator
│   └── avatar.py               # PyQt6 avatar visual feedback
├── mjx/                        # Enterprise modular subsystems
│   ├── intelligence/           # Project OMNIBRAIN
│   ├── agent/                  # Project GHOST
│   ├── skills/                 # Project NEXUS
│   ├── memory/                 # Project CORTEX SQLite storage
│   ├── emotions/               # Project ECHO emotion classifier & momentum
│   ├── security/               # Vault, permissions, emergency stops
│   ├── aurora/                 # Mobile sync protocol & pairing
│   ├── hub/                    # Widget and companion device hub
│   └── evolution/              # Telemetry & metrics collection
├── dashboard/                  # FastAPI local web dashboard
│   └── server.py               # 127.0.0.1 bound remote interface
└── tests/                      # Verification and regression test suite
    ├── test_singularity_integration.py # End-to-end integration tests
    ├── test_cortex_integration.py      # Cortex memory SQLite tests
    ├── test_echo_integration.py        # ECHO voice and emotion tests
    └── test_security_lockdown.py       # Security boundary tests
```
