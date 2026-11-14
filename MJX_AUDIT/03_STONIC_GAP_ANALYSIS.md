# MJ-X VS. STONIC AI — TECHNICAL GAP & CAPABILITY CLASSIFICATION

This document performs an evidence-based comparison between the capabilities observed in **Stonic AI (v3.1.21)** and the actual implementation of **MJ-X**, evaluating each capability against verifiable source code evidence.

---

## 1. COMPREHENSIVE CAPABILITY CLASSIFICATION TABLE

| Capability | Stonic AI Implementation | Existing MJ-X Source Code | Classification | Technical Gap & Required Upgrade |
| :--- | :--- | :--- | :--- | :--- |
| **Real-time Bidirectional Voice** | Gemini 3.5 Transcribe Live + Gemini 3.8 Flash TTS / Gemini Live via Pipecat | Gemini 2.5 Flash Native Audio (`main.py:141`) via GenAI SDK | **IMPLEMENTED** | Low latency streaming works in both; MJ-X lacks VAD gating and session rollover. |
| **Multilingual English / Hinglish** | Prompt instructions + `script: "roman"` phonetic normalization | Native Gemini Live multilingual understanding (`core/prompt.txt`) | **IMPLEMENTED** | Both handle everyday spoken Hindustani and English natively. |
| **Emotion-Aware Responses** | Bracketed prompt performance tags (`[soft and slow]`) injected into TTS engine | 21-state machine with static regex phrases (`emotion/detection.py`) | **PARTIALLY IMPLEMENTED** | MJ-X detects emotions via fragile regex and only alters visual avatar color and volume, not vocal prosody. |
| **Expressive Speech Generation** | Gemini 3.8 Flash TTS chunking + inline tags (`<sigh>`, `<chuckle>`, `<gasp>`) | Gemini Live raw 24kHz PCM stream (`main.py:1770`) | **PARTIALLY IMPLEMENTED** | MJ-X receives standard Gemini speech; lacks inline emotion/breathing tag parsing and sentence-1 isolation. |
| **Smart Turn Detection** | Silero VAD + Smart Turn NLP classifier (`turns.py`) allowing up to 3.0s pause | Server-side Gemini turn completion | **MISSING** | MJ-X cannot detect if user paused to think vs finished speaking; interrupts prematurely. |
| **Aside / Floor Detection** | Floor engine (`floor.py`) emitting `<quiet:aside>` when user talks to others | Always listens and responds to any speech in room | **MISSING** | MJ-X lacks conversational floor awareness and proactive nudge timers (8s, 20s). |
| **Local Silero VAD** | Client-side Silero VAD gate with 1.0s pre-roll buffer (`ears.py`) | Simple RMS math threshold (`_barge_in_threshold`) in `main.py` | **MISSING** | MJ-X continuously streams all microphone silence, wasting massive cloud tokens. |
| **Persistent Contextual Memory** | Verbatim turns + asynchronous LLM digestion into lasting facts | Inverted word token index across 20+ separate JSON files (`memory/`) | **PARTIALLY IMPLEMENTED** | MJ-X stores memories in JSON files; lacks background LLM turn distillation and session compression. |
| **SQLite + FTS5 Phonetic Search** | SQLite3 with FTS5 unicode, trigram (`*_tri`), and consonant-skeleton (`*_skel`) | Regex word tokenization (`\w+`) in `storage.py` | **MISSING** | MJ-X lacks database indexing, BM25 scoring, and Hinglish phonetic transliteration search. |
| **Desktop Presence / Floating Notch** | Apple Dynamic Island top-screen notch + Win32 Living Wallpaper (`WorkerW`) | Traditional 980x700 fixed PyQt6 window (`ui.py`) | **PARTIALLY IMPLEMENTED** | MJ-X has rich QPainter animations but lacks screen-edge docking and click-through transparency. |
| **Vision-Grounded Computer Use** | Resident Agent S3 daemon + UI-TARS 1.5 7B grounding model + Tesseract OCR | Generic Gemini Flash coordinate guessing (`computer_control.py:339`) | **PARTIALLY IMPLEMENTED** | MJ-X uses general LLMs that frequently miss small desktop UI buttons; lacks specialized grounding. |
| **Safety Interruption Mechanisms** | Win32 `WDA_EXCLUDEFROMCAPTURE`, global ESC guard, mouse motion interrupt | PyAutoGUI corner slam only | **PARTIALLY IMPLEMENTED** | MJ-X captures its own UI window during screenshots and lacks an emergency keyboard abort hook. |
| **Dynamic Skills System** | Anthropic Agent Skills standard (`SKILL.md` with YAML frontmatter) | Hardcoded Python action functions in `actions/` | **MISSING** | MJ-X requires editing Python files to add tools; lacks dynamic folder-based skill registration. |
| **Model Context Protocol (MCP)** | Integrated MCP client (`mcp-add`, `mcp-list`, `mcp-test`) | None | **MISSING** | MJ-X cannot connect to external MCP servers (e.g. GitHub, PostgreSQL, Brave Search). |
| **Interactive Visual Hub** | Offscreen sandboxed iframe rendering interactive HTML/CSS/JS diagrams | None (CLI text logs in `LogWidget`) | **MISSING** | MJ-X cannot render interactive charts, visual explainers, or dashboards inside the app. |
| **OS Sensory Awareness** | Win32 watcher tracking active window title, meeting apps (mic usage), video playing | Basic `psutil` CPU/RAM polling in `system_monitor.py` | **PARTIALLY IMPLEMENTED** | MJ-X reads metrics but cannot detect when the user is in a Zoom meeting or watching a film. |
| **Mobile Companion** | PWA connecting via local WebSocket & QR code | Native Android Java app (`android/`) + FastAPI server (`dashboard/`) | **IMPLEMENTED (SUPERIOR)** | MJ-X has a complete native Android companion project with accessibility hooks, exceeding Stonic's basic PWA. |
| **Secure Credential Storage** | Windows DPAPI encryption via Electron `safeStorage` (`stonic-dpapi-v1`) | Plaintext JSON file in `config/api_keys.json` | **MISSING** | MJ-X leaves raw API keys unencrypted on the filesystem. |

---

## 2. REPORT CONTRADICTION & ARTIFACT RECONCILIATION

During the analysis of Stonic AI's codebase versus external claims, several critical contradictions were resolved:

1. **Claim: "Stonic is a purely cloud-based AI assistant."**
   - *Verifiable Reality:* Stonic ships **over 1.2 GB of local software**, including two complete Python virtual environments, local Silero VAD, OnnxRuntime, Agent S3 computer-use daemons, and MediaPipe face recognition models. It is heavily distributed between client and cloud.
2. **Claim: "Stonic executes everything inside Electron."**
   - *Verifiable Reality:* Electron is merely the frontend presentation layer. Audio streaming, voice activity detection, and computer control are strictly executed inside CPython sidecars (`stonic-voice` and `stonic-computer`) communicating via localhost WebSockets and NDJSON.
3. **Claim: "Simple prompt instructions produce realistic emotional delivery in Gemini."**
   - *Verifiable Reality:* Gemini Live audio streaming responds with default prosody unless the backend uses structured TTS styles (`speech_metadata={"style": ...}`) or chunked TTS API calls with explicit emotion tags (`<sigh>`, `<chuckle>`). MJ-X's approach of multiplying PCM samples by a volume float produces zero emotional expression.

---

## 3. SUMMARY OF MJ-X COMPETITIVE ADVANTAGES

While MJ-X lags behind Stonic in VAD gating, memory architecture, and visual grounding, it holds three decisive architectural advantages:
1. **Native Python Performance:** MJ-X runs directly in Python (<120MB RAM vs Stonic's ~1.2GB RAM footprint), making it viable on low-end hardware like the ThinkPad T420.
2. **Zero IPC Serialization:** MJ-X's audio buffers, screen frames, and actions stay inside Python memory without crossing complex Node-to-Python bridges.
3. **Native Android Subsystem:** MJ-X already possesses a native Android Java application with accessibility services and a floating widget, offering deeper mobile integration than a browser PWA.
