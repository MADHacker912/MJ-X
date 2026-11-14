# MJ-X — COMPLETE REPOSITORY & SUBSYSTEM AUDIT
**Repository Location:** `/home/obito/Documents/MJ-X`  
**Auditor:** Senior Software Architect, Python Systems Engineer, AI Agent Engineer & Security Auditor  
**Date:** November 2026  
**Status:** Audit Only — No Source Code Modified  

---

## 1. REPOSITORY OVERVIEW & CODEBASE STRUCTURE

MJ-X is an ambitious Python-based multimodal AI desktop assistant designed to operate with the Google Gemini Live API. Unlike web wrappers or Electron shells, MJ-X runs as a native Python process with a heavily customized PyQt6 interface.

```
/home/obito/Documents/MJ-X/
├── main.py                     # Monolithic orchestrator (2,478 lines)
├── ui.py                       # Monolithic PyQt6 GUI & Custom QPainter HUD (4,150 lines)
├── requirements.txt            # Dependency list (61 packages listed)
├── setup.py                    # Package configuration
├── actions/                    # Tool execution modules (28 Python files)
│   ├── computer_control.py     # PyAutoGUI mouse/keyboard dispatch table
│   ├── autopilot.py            # Vision-guided interaction wrapper
│   ├── screen_processor.py     # Screen/webcam capture via mss & OpenCV
│   ├── web_search.py           # DuckDuckGo search integration
│   ├── send_message.py         # WhatsApp/Telegram message sender
│   ├── reminder.py             # Task scheduler / system reminders
│   ├── system_monitor.py       # psutil resource metrics
│   ├── notes_action.py         # Text notes management
│   ├── dev_agent.py            # Code execution agent
│   └── ponytail.py             # Code simplification utility
├── core/                       # Brain, LLM clients, and learners
│   ├── neural_brain.py         # Custom NumPy MLP code safety classifier
│   ├── self_modifier.py        # Automated codebase AST editor
│   ├── autonomous_learner.py   # Background learning loop
│   ├── llm_client.py           # Alternate text LLM client
│   ├── stt.py / tts.py         # Offline speech fallbacks (vosk, edge-tts)
│   ├── sleep_inhibitor.py      # OS sleep prevention utility
│   └── prompt.txt              # Primary system prompt
├── emotion/                    # Emotion detection & state tracking
│   ├── engine.py               # EmotionEngine coordinator
│   ├── detection.py            # Regex & emoji emotion classifier
│   ├── state.py                # 21 supported emotion state dataclass
│   ├── voice.py                # Volume multiplier PCM utility
│   ├── transitions.py          # State decay mathematics
│   └── avatar.py               # Visual badge state mapping
├── memory/                     # Multi-JSON file memory engine
│   ├── memory_manager.py       # Public memory facade
│   ├── engine.py               # In-memory search & fuzzy matching
│   ├── storage.py              # Inverted index & atomic JSON persistence
│   ├── models.py               # MemoryRecord dataclass
│   └── *.json                  # 20+ category JSON files
├── personality/                # Friend personality & disagreement rules
│   ├── config.py               # Traits and relationship configuration
│   └── disagreement.py         # Counter-argument generation
├── dashboard/                  # Remote web interface (FastAPI + WebSocket)
│   ├── server.py               # Port 8000 AES-256 encrypted server
│   └── static/                 # login.html & app.html
├── bridges/                    # WhatsApp bridge & multi-device sync
│   ├── bridge_manager.py       # Bridge lifecycle
│   └── whatsapp_bridge.py      # WhatsApp web socket automation
├── android/                    # Native Android companion application
│   ├── app/src/main/           # Java sources (MJFloatingService, VoiceEngine)
│   └── bin/                    # Precompiled APKs (MJ-X-Assistant.apk)
└── config/                     # Configuration & credentials
    ├── api_keys.json           # Plaintext API keys & UI settings
    └── channels.json           # Messaging channel definitions
```

---

## 2. SUBSYSTEM-BY-SUBSYSTEM DETAILED AUDIT

### 2.1. Main Orchestrator & Execution Loop (`main.py`)
- **File:** [main.py](file:///home/obito/Documents/MJ-X/main.py) (2,478 lines)
- **Primary Classes & Coroutines:** `_listen_audio()`, `_send_realtime()`, `_receive_audio()`, `_play_audio()`, `_execute_tool()`, `run()`.
- **What Works:**
  - Establishes a live bidirectional WebSocket session with Google Gemini Live (`models/gemini-2.5-flash-native-audio-preview-12-2025`).
  - Successfully routes raw 16kHz audio input to Gemini and streams 24kHz audio output to the local speaker via `sounddevice`.
  - Dispatches tool calls returned by Gemini to corresponding Python action functions.
- **What Is Partially Implemented:**
  - Barge-in detection (`_barge_in_threshold`) uses a crude RMS math heuristic (`max(650.0, ambient_rms * 3.2, output_rms * 0.22)`). It frequently misfires under variable room acoustics or speaker bleed.
  - Interruption handler splits audio into ~50ms slices (`_SLICE = 2400`), but does not cleanly flush pending network audio queues.
- **What Is Missing:**
  - **No Local Voice Activity Detection (VAD) Gating:** Lines 1712–1718 stream *every single audio frame* continuously to Google, burning API quota on silence.
  - **No Turn-taking Intelligence:** Relies entirely on remote server-side turn termination, causing unnatural interruptions when the user pauses mid-sentence.
  - **No Conversational Floor Awareness:** Cannot distinguish if the user is talking to the assistant, talking to a family member, or on a phone call.
- **Bugs & Weaknesses:**
  - Severe architectural bloat: 2,478 lines containing global monkey patches (`subprocess.Popen` overriding, Xlib auth hacking), 40+ tool declarations, audio loops, background tasks, and UI coordination all in one file.
  - Global mutable state with multiple intersecting locks (`self._speaking_lock`, `self._voice_interrupt_pending`).
- **Verdict:** **REPLACE / MODULARIZE.** Split into a decoupled `AudioEngine`, `SessionManager`, and `ToolDispatcher`.

---

### 2.2. Presentation Layer (`ui.py`)
- **File:** [ui.py](file:///home/obito/Documents/MJ-X/ui.py) (4,150 lines)
- **Primary Classes:** `MJUI`, `MainWindow`, `HudCanvas`, `AvatarBadge`, `MetricBar`, `LogWidget`, `SetupOverlay`, `CustomizeOverlay`.
- **What Works:**
  - Impressive, highly tailored visual aesthetics with custom QPainter graphics (rotating conical gradients, pulsing circular rings, dynamic audio waveforms).
  - Real-time CPU, RAM, and GPU telemetry rendering via `_SysMetrics` and `psutil`.
  - Dynamic palette derivation (`apply_ui_accent`) shifting all UI colors based on a single hex value.
  - Drag-and-drop file ingestion zone (`FileDropZone`).
- **What Is Partially Implemented:**
  - Camera overlay (`_CameraPreview`): displays a crude border overlay rather than a smooth responsive feed.
- **What Is Missing:**
  - **No Frameless Top-Screen Notch ("Dynamic Island"):** The window is a traditional 980x700 fixed desktop window; it cannot dock to the screen edge or remain unobtrusively visible during work.
  - **No Click-Through Transparency:** Does not support `WA_TransparentForMouseEvents` to allow users to interact with desktop apps behind transparent areas.
  - **No Sandboxed Visual Hub:** Cannot render rich HTML/CSS artifacts (diagrams, timelines, dashboards) generated by AI.
- **Bugs & Weaknesses:**
  - 4,150 lines in a single file makes maintenance precarious.
  - Uses raw `ctypes` Windows API calls inside UI paint loops without robust cross-platform guards.
- **Verdict:** **RETAIN & REFINE.** The custom QPainter HUD and visual identity are among MJ-X's strongest assets. Refactor `ui.py` into smaller widget modules and build a dedicated `DesktopNotch` component.

---

### 2.3. Audio Pipeline & Speech Engine (`main.py`, `core/stt.py`, `core/tts.py`)
- **Files:** [main.py](file:///home/obito/Documents/MJ-X/main.py#L1671-L1780), [core/stt.py](file:///home/obito/Documents/MJ-X/core/stt.py), [core/tts.py](file:///home/obito/Documents/MJ-X/core/tts.py)
- **What Works:**
  - Low-latency full-duplex streaming using `sounddevice.InputStream` (16kHz PCM) and `sounddevice.OutputStream` (24kHz PCM).
- **What Is Partially Implemented:**
  - `core/stt.py` (Vosk / Faster-Whisper) and `core/tts.py` (Kokoro / Edge-TTS) exist as local offline fallback stubs, but they are completely bypassed in `main.py` which talks directly to Gemini Live.
- **What Is Missing:**
  - **No Silero VAD:** No local neural model to detect human speech boundaries before sending data over the network.
  - **No Pre-roll Circular Buffer:** When speaking begins after silence, the initial consonant is frequently clipped.
  - **No Connection Handover:** Does not handle long-session WebSocket disconnects gracefully.
- **Bugs & Weaknesses:**
  - Heavy CPU and network utilization on low-spec systems due to unthrottled streaming of continuous background noise.
- **Verdict:** **IMPROVE.** Introduce a local `SileroVADGatedStream` with 1.0s pre-roll and 0.8s hangover buffer in front of `main.py`'s out-queue.

---

### 2.4. Emotion & Personality Engine (`emotion/`, `personality/`)
- **Files:** [emotion/engine.py](file:///home/obito/Documents/MJ-X/emotion/engine.py), [emotion/detection.py](file:///home/obito/Documents/MJ-X/emotion/detection.py), [emotion/voice.py](file:///home/obito/Documents/MJ-X/emotion/voice.py)
- **What Works:**
  - State machine supporting 21 emotional states (`happy`, `sad`, `excited`, `caring`, `serious`, etc.) with transition decay (`transitions.py`).
  - Visual reflection: The `AvatarBadge` and HUD change color and pulsation based on detected emotion.
- **What Is Partially Implemented:**
  - Emotion detection (`detection.py`): Relies entirely on static regex keywords (`haha`, `lol`, `bohot gussa`) and emojis. It completely fails on nuanced, sarcastic, or contextual emotional cues.
- **What Is Missing:**
  - **No Expressive Voice Synthesis:** `emotion/voice.py` simply multiplies raw PCM samples by a volume float (`samples *= volume`). It **cannot** change pitch, inflection, breathing, or vocal delivery because Gemini Live returns pre-synthesized PCM audio.
  - **No Inline Tag Translation:** Does not support performance tags (`[soft and slow]`, `<sigh>`, `<laugh>`) as seen in modern voice engines.
- **Bugs & Weaknesses:**
  - Creates an illusion of emotional speech in code that does not actually materialize in the speaker output.
- **Verdict:** **REDESIGN.** Replace static regex with prompt-driven performance cues that Gemini Live natively interprets in audio generation.

---

### 2.5. Memory & Storage Architecture (`memory/`)
- **Files:** [memory/storage.py](file:///home/obito/Documents/MJ-X/memory/storage.py), [memory/engine.py](file:///home/obito/Documents/MJ-X/memory/engine.py), [memory/memory_manager.py](file:///home/obito/Documents/MJ-X/memory/memory_manager.py)
- **What Works:**
  - Atomic JSON file writing via temporary files prevents file corruption during crashes.
  - Inverted token index in memory speeds up simple keyword lookups.
  - Backup creation in `memory/backups/`.
- **What Is Partially Implemented:**
  - Inverted index only indexes alphanumeric word tokens (`re.findall(r"[\w]+", text)`); it cannot handle typos, phonetic variations, or partial phrases.
- **What Is Missing:**
  - **No SQLite:** Relies on 20+ separate JSON files (`facts.json`, `preferences.json`, `habits.json`, `semantic_memory.json`), creating severe disk I/O thrashing.
  - **No FTS5 Full-Text Search:** Lacks full-text search, BM25 ranking, and trigram fuzzy matching.
  - **No Hinglish Phonetic Skeleton Indexing:** Cannot equate "mujhe jana hai" with "mujhe jaana h" or Urdu script "جانا".
- **Bugs & Weaknesses:**
  - Scalability limit: Reading and rewriting multiple JSON files on low-spec hardware (HDD or slow SATA SSD on ThinkPad T420) introduces UI micro-stutters.
- **Verdict:** **REPLACE.** Migrate entirely to a single `memory.db` SQLite database with FTS5 virtual tables (`*_uni`, `*_tri`, `*_skel`).

---

### 2.6. Multimodal Perception & Desktop Automation (`actions/`, `core/`)
- **Files:** [actions/computer_control.py](file:///home/obito/Documents/MJ-X/actions/computer_control.py), [actions/screen_processor.py](file:///home/obito/Documents/MJ-X/actions/screen_processor.py), [actions/autopilot.py](file:///home/obito/Documents/MJ-X/actions/autopilot.py)
- **What Works:**
  - Screen capture using `mss` is fast and lightweight.
  - Mouse clicking, typing, scrolling, and window activation work via PyAutoGUI and OS-specific scripts.
- **What Is Partially Implemented:**
  - Visual element search (`_screen_find`): Takes a screenshot, uploads it to `gemini-3.6-flash`, and asks for `x,y` center coordinates. While functional for large prominent buttons, general LLMs have high coordinate error rates on dense UI interfaces.
- **What Is Missing:**
  - **No Specialized Visual Grounding Model:** Missing UI-TARS 1.5 7B integration for reliable pixel coordinates.
  - **No Capture Exclusion (`WDA_EXCLUDEFROMCAPTURE`):** MJ-X captures its own UI window when taking screenshots, causing confusion for vision models.
  - **No Emergency Keyboard Interruption:** Missing a global ESC key listener to abort runaway automation.
  - **No Permission Guardrails:** Executes clicks, typing, and OS commands without explicit user confirmation for sensitive actions.
- **Bugs & Weaknesses:**
  - High risk of unintended destructive actions if the vision model misidentifies coordinates.
- **Verdict:** **IMPROVE & SECURE.** Add UI-TARS API grounding, a dedicated non-capturable HUD overlay, global ESC abort, and permission prompts for critical actions.

---

### 2.7. Bridges, Dashboard & Mobile Companion (`bridges/`, `dashboard/`, `android/`)
- **Files:** [dashboard/server.py](file:///home/obito/Documents/MJ-X/dashboard/server.py), [android/](file:///home/obito/Documents/MJ-X/android)
- **What Works:**
  - `dashboard/server.py` runs a complete FastAPI + WebSocket server on port 8000 with custom AES-256 application-layer encryption.
  - The `android/` directory contains a functional, native Android companion application with an accessibility service and floating overlay (`MJFloatingService.java`).
- **What Is Partially Implemented:**
  - Mobile web experience: `static/app.html` provides basic remote chat, but lacks a full responsive PWA manifest and mobile microphone voice streaming.
- **What Is Missing:**
  - Seamless QR-code pairing between desktop and mobile PWA.
- **Verdict:** **RETAIN & LEVERAGE.** MJ-X's native Android implementation and FastAPI dashboard are significant architectural strengths that Stonic AI lacks.

---

### 2.8. Configuration & Credential Security (`config/`)
- **File:** [config/api_keys.json](file:///home/obito/Documents/MJ-X/config/api_keys.json)
- **What Works:**
  - Reads and writes application settings reliably.
- **What Is Missing / Critical Security Risk:**
  - **Plaintext API Keys:** `gemini_api_key` is stored in unencrypted JSON on disk. Any process or malware on the host system can read it immediately.
- **Verdict:** **REPLACE.** Move credential storage to OS-native secure enclaves (Windows DPAPI, Linux SecretService, or `keyring`).
