# ⚡ MJ-X (Mark-L)
### The Ultimate Cross-Platform Autonomous AI Assistant & Multimodal Agent Engine

> **Created & Developed by [Saksham Gupta](https://github.com/MADHacker912)** ([@MADHacker912](https://github.com/MADHacker912))

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-Live%20Multimodal%20API-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6%20Cyberpunk%20HUD-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-blue?style=for-the-badge&logo=linux&logoColor=white)](https://github.com)
[![Creator](https://img.shields.io/badge/Creator-Saksham%20Gupta-8A2BE2?style=for-the-badge&logo=github&logoColor=white)](https://github.com/MADHacker912)
[![Status](https://img.shields.io/badge/Status-Active%20Development-success?style=for-the-badge)](https://github.com)

---

## 📖 Table of Contents
- [🌟 Overview](#-overview)
- [🧠 Architecture & Flow](#-architecture--flow)
- [✨ Core Capabilities](#-core-capabilities)
  - [1. Real-Time Multimodal Voice & Vision](#1-real-time-multimodal-voice--vision)
  - [2. Deep Cognitive Memory Engine (v2)](#2-deep-cognitive-memory-engine-v2)
  - [3. OS-Level Automation & Computer Control](#3-os-level-automation--computer-control)
  - [4. Developer Agent & Minimalist Coding Engine](#4-developer-agent--minimalist-coding-engine)
  - [5. Multi-Channel Bridges & Remote Dashboard](#5-multi-channel-bridges--remote-dashboard)
  - [6. Personality & Emotion Architecture](#6-personality--emotion-architecture)
  - [7. Proactive Assistant & Hardware Telemetry](#7-proactive-assistant--hardware-telemetry)
- [🗂️ Repository Structure](#️-repository-structure)
- [⚡ Quick Start & Installation](#-quick-start--installation)
- [⚙️ Configuration](#️-configuration)
- [⚠️ Current Limitations & Known Issues (WIP)](#️-current-limitations--known-issues-wip)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 Contributing & Community](#-contributing--community)
- [📄 License & Attribution](#-license--attribution)

---

## 🌟 Overview

**MJ-X** is an autonomous, real-time AI assistant and cognitive agent designed to act as an omnipresent desktop co-pilot and personal executive system. Unlike standard chatbots that operate strictly within browser sandboxes, MJ-X has direct OS-level execution capability, screen perception, real-time bidirectional voice streaming, multi-channel messaging bridges, and an indexed long-term memory system.

Built on the **Google Gemini Live API**, MJ-X bridges speech, vision, background intelligence, and system automation into a unified, zero-subscription desktop companion.

---

## 🧠 Architecture & Flow

```
                      ┌──────────────────────────────┐
                      │    User Voice / Input / HUD  │
                      └──────────────┬───────────────┘
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │                 MJ-X Core Orchestrator                  │
        │  (Audio Capture, PyQt6 Cyberpunk HUD, Event Loop)        │
        └──────────────┬───────────────────────────┬──────────────┘
                       │                           │
                       ▼                           ▼
        ┌─────────────────────────────┐  ┌─────────────────────────────┐
        │   Google Gemini Live API    │  │   Cognitive Memory Engine   │
        │ (Bidirectional Audio/Vision)│  │ (Categorized Inverted Index)│
        └──────────────┬──────────────┘  └──────────────┬──────────────┘
                       │                                │
                       ▼                                ▼
        ┌─────────────────────────────────────────────────────────┐
        │             Agent Tool Dispatcher & Engine              │
        ├─────────────────────────────┬───────────────────────────┤
        │ 🖥️ OS & Computer Control    │ 💻 Developer Agent & Dev  │
        │ 👁️ Screen & Camera Vision   │ 📱 WhatsApp / Bridges     │
        │ 🔍 Dual Parallel Web Search │ 📊 Hardware Telemetry     │
        │ ⏰ Scheduled Reminders      │ 🎭 Emotion & Tone Filter  │
        └─────────────────────────────┴───────────────────────────┘
```

---

## ✨ Core Capabilities

### 1. Real-Time Multimodal Voice & Vision
- **Ultra-Low Latency Speech**: Bidirectional voice streaming via Gemini Live API with instant interruption support.
- **Screen Perception**: Real-time multi-monitor capture and analysis (`screen_process`) enabling MJ to read code, errors, documents, or UI layouts.
- **Webcam Awareness**: Live visual feed through connected cameras for contextual real-world perception.
- **Feminine Hinglish/English Synthesis**: Natural, emotive conversational cadence with context-aware verb inflections.

### 2. Deep Cognitive Memory Engine (v2)
- **Categorized Atomic JSON Stores**: Granular segregation (`skills`, `projects`, `identity`, `preferences`, `habits`, `facts`, `schedule`, `devices`, `notes`).
- **Inverted Token Indexing**: High-speed token-based search and fuzzy query resolution for lightning-fast memory retrieval.
- **Confidence & Reinforcement Lifecycle**: Automatically decays stale memories, reinforces verified facts, and manages contradiction resolution.
- **Learned Agent Skills**: Retains deep technical patterns, engineering workflows, and system skills permanently in `skills.json`.
- **Zero Memory Bloat**: Session summaries are dynamically compressed and consumed without polluting long-term factual state.

### 3. OS-Level Automation & Computer Control
- **Cross-Platform System Controls**: Adjust volume, brightness, power state, WiFi toggles, and OS shortcuts across Linux, Windows, and macOS.
- **Application & Browser Management**: Launch, close, and manage local desktop applications and browser tabs natively.
- **File System Operations**: Create, move, delete, read, and summarize local workspace documents and directories.

### 4. Developer Agent & Minimalist Coding Engine
- **Dev Agent (`dev_agent.py`)**: Multi-file project scaffolding, automated debugging, and code generation.
- **Ponytail Philosophy (`ponytail.py`)**: Enforces senior-dev minimalist principles — YAGNI (You Aren't Gonna Need It), standard library first, deletion over addition, zero boilerplate.
- **SlopWatch AI Anti-Cheat (`slopwatch.py`)**: Detects reward hacking, fake test passes, suppressed warnings, and dead AI boilerplate.

### 5. Multi-Channel Bridges & Remote Dashboard
- **WhatsApp Bridge (`whatsapp_bridge.py`)**: Integrated Node.js/Baileys gateway for automated message summaries, unread alerts, and natural contact responses.
- **Remote Web Dashboard (`dashboard/`)**: Instant QR-code mobile pairing to control MJ-X securely from any smartphone on the local network.
- **Multi-Platform Webhook Ready**: Modular architecture ready for Discord, Telegram, and Instagram integrations.

### 6. Personality & Emotion Architecture
- **Multi-Mode Conversation Engine**: Seamless transition between *Casual Friend*, *Honest Advisor*, *Teacher*, *Supportive*, *Serious Warning*, and *Debate* modes.
- **Truth-Over-Agreement**: Corrects user fallacies respectfully rather than offering superficial validation or sycophancy.
- **Emotion Engine**: Real-time affective state (joy, curiosity, focus, calm, empathy) that subtly modulates TTS cadence, typing speed, and HUD status expressions.

### 7. Proactive Assistant & Hardware Telemetry
- **Morning Briefing**: Automatically greets you on first launch, delivers time-aware updates, recaps pending tasks, and fetches live news.
- **Topic Watcher (`background_monitor.py`)**: Watches configured news topics in the background and reports when major developments break.
- **Hardware Guardian (`system_monitor.py`)**: Continuous telemetry for CPU usage, RAM consumption, GPU load, and temperature thresholds with voice alarms.

---

## 🗂️ Repository Structure

```
MJ-X/
├── main.py                     # Primary runtime loop & Gemini Live stream coordinator
├── ui.py                       # PyQt6 Cyberpunk HUD (waveform, terminal, dynamic display)
├── setup.py                    # First-run automated setup & diagnostic wizard
├── requirements.txt            # Python dependencies
├── core/
│   ├── prompt.txt              # Core personality & strict tool-routing protocols
│   ├── llm_client.py           # Gemini API client wrapper & tool definitions
│   ├── neural_brain.py         # Neural cognitive dispatch & decision loop
│   ├── stt.py & tts.py         # Speech-to-text & Text-to-speech audio drivers
│   └── self_modifier.py        # Code self-modification & hot-reloading engine
├── memory/
│   ├── models.py               # Memory schema contracts & dataclasses
│   ├── storage.py              # Atomic JSON storage, caching & inverted index
│   ├── engine.py               # MemoryEngine orchestrator & confidence scoring
│   ├── config_manager.py       # Runtime memory configuration & auto-backup
│   ├── skills.json             # Permanent learned architectural & coding skills
│   └── memory_index.json       # Inverted token search index
├── actions/
│   ├── screen_processor.py     # Real-time screen capture & webcam vision
│   ├── web_search.py           # Parallel Gemini Grounded + DuckDuckGo search
│   ├── computer_settings.py    # Volume, brightness, WiFi, power controls
│   ├── computer_control.py     # Keyboard, mouse, shortcuts, window manager
│   ├── dev_agent.py            # Autonomous multi-file project developer
│   ├── ponytail.py             # Minimalist senior-dev code simplification
│   ├── slopwatch.py            # AI anti-cheat & slop detection
│   ├── background_monitor.py   # Daily background topic watcher
│   ├── system_monitor.py       # Hardware telemetry & resource alerts
│   └── whatsapp_action.py      # WhatsApp contact & messaging dispatcher
├── personality/
│   ├── engine.py               # Personality planning & mode detection
│   ├── disagreement.py         # Truth-over-agreement claim evaluator
│   └── prompts/                # Behavioral prompts (friend, system, format)
├── bridges/
│   └── whatsapp_bridge.py      # Webhook receiver & Baileys gateway bridge
├── dashboard/                  # Remote web control interface & mobile pairing
└── config/
    ├── api_keys.json           # API keys, OS settings, user preferences
    └── channels.json           # Messaging channel whitelist & bridge configs
```

---

## ⚡ Quick Start & Installation

### 1. Prerequisites
- **Python**: Version `3.11` or `3.12` recommended.
- **PortAudio / Audio Drivers**:
  - **Linux (Ubuntu/Debian)**: `sudo apt update && sudo apt install -y portaudio19-dev python3-pyaudio libasound2-dev`
  - **macOS**: `brew install portaudio`
  - **Windows**: PyAudio wheels are installed automatically via pip.
- **Google Gemini API Key**: Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).

### 2. Clone and Install
```bash
# Clone the repository
git clone https://github.com/MADHacker912/MJ-X.git
cd MJ-X

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Credentials
Edit `config/api_keys.json`:
```json
{
    "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
    "os_system": "linux",
    "morning_brief_enabled": true,
    "assistant_name": "MJ",
    "user_name": "Boss",
    "ui_color": "#ff2a8d",
    "camera_index": 0,
    "voice_interruption_enabled": true,
    "tts_voice_gender": "female"
}
```

### 4. Run MJ-X
```bash
python3 main.py
```

---

## ⚠️ Current Limitations & Known Issues (WIP)

While MJ-X is functional and daily-drivable, the following known challenges are actively being improved:

1. **Gemini Live Rate Limits on Free Tier**:
   - *Issue*: High-frequency multimodal streaming (continuous audio + rapid 4K screenshot dispatch) can hit Gemini Live API token/request quotas on standard free keys.
   - *Mitigation*: Adaptive vision frame throttling and fallback caching are currently implemented.

2. **OS Audio Loopback & Permissions (Linux/macOS)**:
   - *Issue*: On specific Linux audio servers (such as PipeWire configurations without ALSA compatibility layers) or macOS privacy sandboxes, microphone capture or TTS audio playback may require explicit permission grants or driver mapping.
   
3. **WhatsApp Webhook Gateway Dependency**:
   - *Issue*: The WhatsApp bridge depends on an auxiliary Node.js/Baileys micro-service running locally. If the Node process drops or QR authentication expires, messaging fallback relies on desktop notifications.

4. **Screen Capture Latency on High-Resolution Multi-Displays**:
   - *Issue*: Capturing 4K multi-monitor layouts simultaneously can cause a ~500ms–1.5s latency spike before sending payloads to the vision model.
   - *Mitigation*: Region-of-interest cropping and adaptive image downsampling are in progress.

5. **Sandbox Isolation for Code Execution**:
   - *Issue*: `dev_agent.py` and `code_helper.py` execute and modify files directly in the target workspace. An isolated containerized runtime (Docker / WebAssembly sandbox) is planned for safer autonomous code execution.

6. **Hardware Telemetry on Non-NVIDIA / Virtual Environments**:
   - *Issue*: GPU temperature and VRAM monitoring currently rely on NVIDIA NVML / `nvidia-smi`. Systems with Intel/AMD integrated GPUs default to CPU/RAM telemetry only.

---

## 🗺️ Roadmap

- [x] **Phase 1: Foundation** — Real-time Gemini Live audio streaming, PyQt6 HUD, basic OS automation.
- [x] **Phase 2: Cognitive Memory** — Inverted index memory engine v2, confidence scoring, learned skills bank.
- [x] **Phase 3: Multimodal Vision & Bridges** — Instant screen perception, WhatsApp bridge, remote mobile dashboard.
- [ ] **Phase 4: Sandboxed Code Execution** — Dockerized agent environment for safe autonomous coding.
- [ ] **Phase 5: Offline Local LLM Fallback** — Ollama / llama.cpp seamless failover when internet drops.
- [ ] **Phase 6: Multi-Device Sync** — Peer-to-peer encrypted memory synchronization across multiple machines.

---

## 🤝 Contributing & Community

Contributions, issues, and feature suggestions are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License & Attribution

- **License**: Personal and non-commercial development. Licensed under [Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/).
- **Original Creator & Architect**: **[Saksham Gupta](https://github.com/MADHacker912)** ([@MADHacker912](https://github.com/MADHacker912))
- **Core Engine**: Powered by Google Gemini Live API & PyQt6.

---

<p align="center">
  <b>⭐ Star this repository if you find MJ-X inspiring or useful! ⭐</b>
</p>
