# ⚡ MJ (Genesis & Singularity Edition)
### Autonomous Multimodal AI Ecosystem, Real-Time Bidirectional Voice & Cognitive Desktop Engine

> **Created & Developed by [Saksham Gupta](https://github.com/MADHacker912)** ([@MADHacker912](https://github.com/MADHacker912))  
> *Production-Grade Personal Artificial Intelligence Assistant & Autonomous Operating System Companion*

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Gemini Live](https://img.shields.io/badge/Google%20Gemini-Live%20Multimodal%20WebSocket%20API-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6%20Cyberpunk%20HUD-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![Tests](https://img.shields.io/badge/Test%20Suite-187%2F187%20Passing%20(100%25)-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![Security](https://img.shields.io/badge/Security-OS%20Vault%20%7C%20Zero%20Secrets%20Leaked-red?style=for-the-badge&logo=security&logoColor=white)](https://owasp.org)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Desktop%20%7C%20Android-blue?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/MADHacker912/MJ-X)

---

## 🌟 What is MJ?

**MJ** is not a toy chatbot or an API wrapper. It is a full-stack, local-first, multimodal autonomous AI operating environment designed to run natively on your machine. Powered by the bidirectional streaming **Google Gemini Live API**, MJ sees your desktop, listens to your voice with sub-second latency, executes complex OS workflows, manages its own long-term relational memory, responds with contextual emotional intelligence, and links across your desktop, phone, and messaging platforms.

```
                           ╔═══════════════════════════════════════╗
                           ║        MJ UNIFIED INTELLIGENCE        ║
                           ╚═══════════════════════╦═══════════════╝
                                                   ║
                ┌──────────────────────────────────╫──────────────────────────────────┐
                ▼                                  ▼                                  ▼
   ┌─────────────────────────┐        ┌─────────────────────────┐        ┌─────────────────────────┐
   │    MULTIMODAL CORE      │        │      COGNITIVE BRAIN    │        │    SYSTEM SECURITY      │
   │  - Gemini Live WS 1011  │        │  - Autonomous Planner   │        │  - OS Secret Vault      │
   │  - Fault-Tolerant Jitter│        │  - Context Engine       │        │  - Sandbox Process Mgr  │
   │  - Bidirectional Audio  │        │  - Reasoning Engine     │        │  - Emergency Stop Gate  │
   │  - 30 FPS Screen Vision │        │  - ReAct Decision Loop  │        │  - Category RBAC System │
   └────────────┬────────────┘        └────────────┬────────────┘        └────────────┬────────────┘
                │                                  │                                  │
                └──────────────────────────────────╫──────────────────────────────────┘
                                                   ▼
                           ┌───────────────────────────────────────────────┐
                           │            UNIFIED RUNTIME KERNEL             │
                           │  - Cortex SQLite WAL Local-First Memory Engine│
                           │  - Echo Emotional Inertia & Decay Dynamics    │
                           │  - 40+ Desktop & System Automation Tools      │
                           │  - Android Companion & Localhost Dashboard    │
                           └───────────────────────────────────────────────┘
```

---

## 🚀 Key Architectural Pillars

### 1. Gemini Live Bidirectional Streaming with 1011 Auto-Recovery
- Sub-second, full-duplex conversational voice using direct WebSocket streaming over Google's native GenAI Live API.
- **Fault-Tolerant WebSocket Resilience**: Automatic detection and transparent recovery from transient server drops (`1011 Internal error occurred` and `1006 TCP reset`) with exponential backoff, $\pm 25\%$ randomized jitter, and 20s stability reset detection.
- **Two-Tier TaskGroup Decoupling**: Application background services (system telemetry, memory compaction, proactive monitors) run uninterrupted during transient socket disconnects without crashing or resetting intervals.
- Hardware-level audio stream cleanup (`sd.InputStream` / `sd.OutputStream`) and buffer purging to eliminate stale audio lag.

### 2. Cortex Unified Memory Engine
- **Local-First SQLite Repository with WAL Mode**: High-performance transaction isolation with millisecond query speeds.
- **Full-Text Search (FTS5) & Semantic Ranking**: BM25 relevance scoring combined with Hinglish normalization (phonetic folding for Hinglish, Hindi, and English prompts).
- **Automated Memory Compaction & Provenance Tracking**: Tracks timestamps, confidence metrics, source modality, and automated background backups.

### 3. Echo Emotion & Affective Dynamics
- **Continuous 5-Dimensional Emotional State**: Tracks *valence, arousal, dominance, engagement,* and *sentiment*.
- **Emotion Inertia & Decay Physics**: Inferred emotions naturally decay toward baseline over time without permanent sensitive labeling.
- **Context-Adaptive Voice & Speech Modulation**: Responses intelligently shift tone between playful banter, empathetic listening, and concise technical precision.

### 4. P0 Security Lockdown & OS Credential Vault
- **Zero Hardcoded Secrets**: Credentials, keys, and tokens are stored in the OS-native Secret Service / Keychain via cryptographic vault abstraction.
- **Subprocess Sandboxing & Execution Timeouts**: All shell tasks execute through `safe_run` and `safe_spawn` with strict argument validation, directory restrictions, and emergency stop enforcement.
- **Localhost-Bound Telemetry Dashboard**: The FastAPI companion dashboard binds strictly to `127.0.0.1` by default, protected by session security.

### 5. Multimodal Desktop Perception & Automation
- **Real-Time Screen & Camera Vision**: Analyze active IDE code, terminal traces, browser windows, and desktop layouts.
- **Cross-Platform Computer Control**: Mouse positioning, keyboard automation, window management, audio controls, and application launching.
- **WhatsApp Bridge & Android Companion**: Direct synchronization with your phone via QR bridge and local socket companion.

---

## 🛠️ Complete Subsystem Architecture

| Subsystem | Location | Description |
| :--- | :--- | :--- |
| **Live Recovery** | `mjx/live/` | `LiveSessionManager`, `ReconnectPolicy`, `LiveErrorClassifier`, connection state machine |
| **Intelligence Core** | `mjx/intelligence/` | `Brain`, `Planner`, `ContextEngine`, `ReasoningEngine`, `DecisionEngine` |
| **Cortex Memory** | `mjx/memory/` | SQLite WAL engine, FTS5 Hinglish search, backup/restore, legacy compatibility |
| **Echo Affective** | `mjx/emotions/` | Real-time sentiment classifier, emotion inertia physics, personality adaptation |
| **Security & Vault**| `mjx/security/` | OS Vault credential store, sandboxed process manager, category RBAC, emergency stop |
| **Skills Ecosystem**| `mjx/skills/` | Dynamic tool discovery, self-evolving skill registry, execution sandbox |
| **Desktop Automation**| `actions/` | Screen capture, computer control, web search, media players, developer tools |
| **FastAPI Dashboard**| `dashboard/` | Localhost real-time HUD, memory browser, hardware telemetry, command center |

---

## ⚡ Quick Start

### 1. Prerequisites
- **Linux** (Ubuntu, Debian, Arch, Fedora) or **macOS**
- **Python 3.11+** (Tested on Python 3.11, 3.12, 3.14)
- **PortAudio** & system libraries:
  ```bash
  sudo apt-get update && sudo apt-get install -y portaudio19-dev libasound2-dev libgl1-mesa-glx
  ```

### 2. Clone and Setup
```bash
git clone https://github.com/MADHacker912/MJ-X.git mj
cd mj

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Store API Key Securely in Vault
```bash
python3 -c "from mjx.security import set_api_key; set_api_key('gemini', 'YOUR_GEMINI_API_KEY'); print('API key secured!')"
```

### 4. Run MJ
```bash
# Terminal mode
python3 main.py --terminal

# Full Cyberpunk PyQt6 GUI HUD
python3 main.py
```

---

## 🧪 Automated Test Suite (187 / 187 Passing)

Every capability in MJ is continuously verified with real automated tests (zero mock fabrication):

```bash
PYTHONPATH=. pytest tests/ -v
```

```
======================== 187 passed, 6 warnings in 56.37s ========================
```

- `tests/test_websocket_recovery.py`: 14/14 PASSED (1011 transient disconnect, backoff jitter, task isolation)
- `tests/test_vault.py`: 18/18 PASSED (OS credential vault, secret isolation)
- `tests/test_permissions.py`: 15/15 PASSED (Fine-grained category grants & emergency stop)
- `tests/test_process_manager.py`: 12/12 PASSED (Safe execution, sandbox timeouts)
- `tests/test_security_lockdown.py`: 12/12 PASSED (Self-modification & dashboard binding)
- `tests/test_local_memory.py`: 14/14 PASSED (FTS5 search, Hinglish normalization)
- `tests/test_cortex_integration.py`: 22/22 PASSED (Unified SQLite schema, deduplication)
- `tests/test_emotions_ecosystem.py`: 16/16 PASSED (Emotion classification, decay)
- `tests/test_echo_integration.py`: 19/19 PASSED (Voice turn taking, audio frames)
- `tests/test_intelligence_core.py`: 14/14 PASSED (Brain, planner, reasoning engine)
- `tests/test_singularity_integration.py`: 16/16 PASSED (End-to-end multimodal integration)

---

## 🛡️ Security & Privacy Philosophy

1. **Local-First Data Storage**: All memories, conversational histories, and embeddings reside exclusively on your local device in encrypted/protected SQLite databases.
2. **Zero Plaintext Credentials**: API keys are never written to disk files or git commits. They are isolated in operating system keychains.
3. **No Unrestricted Self-Modification**: Administrative approval is required before modifying source files, preventing prompt injection attacks.
4. **Instant Emergency Stop**: Hardware killswitch halts all active processes, audio streams, and outbound requests instantaneously.

---

## 👨‍💻 Author & Technical Skills

Developed with passion and systems precision by **Saksham Gupta**  
- **GitHub**: [@MADHacker912](https://github.com/MADHacker912)  
- **LinkedIn**: [Saksham Gupta](https://www.linkedin.com/in/saksham-gupta-9125obito/)  
- **Product Hunt**: [@saksham_gupta22](https://www.producthunt.com/@saksham_gupta22)  
- **Portfolio**: [sakshamgupta.online](https://sakshamgupta.online)

### 🚀 Core Engineering Competencies & Stack:
- **Multimodal AI & Autonomous Agents**: Bidirectional duplex voice streaming, Google Gemini Live WebSocket API, low-latency agent harnesses, tool execution engines, cognitive indexed memory (`SQLite WAL + FTS5` semantic search).
- **Full-Stack Systems & Architecture**: Python (AsyncIO, FastAPI, PySide6/PyQt6 Cyberpunk HUD), Linux systems programming, IPC/DBus protocols, systemd automation, high-concurrency background services.
- **Offensive Security & Reverse Engineering**: Binary analysis, AST-level static analysis, credential vaulting & OS sandboxing, APK/Electron reverse engineering, OWASP compliance.
- **Frontend & Visual Engineering**: Anti-AI slop design standards, custom hardware telemetry HUDs, TypeScript, Three.js / WebGL, GSAP motion systems.
- **Mobile & Cross-Platform**: Android native (Kotlin, Jetpack Compose), background device telemetry synchronization.

---

## 📄 License

Distributed under the Apache 2.0 License. See `LICENSE` for details.
