# MJ-X GENESIS FINAL REPORT — 10: VISUAL WORKSPACE

**Subsystem:** Real-Time Visual Workspace, Widget Dispatcher & Responsive UI Hub (Project MIRROR)  
**Package:** `mjx.hub`, `dashboard/`  

---

## 1. VISUAL WORKSPACE ARCHITECTURE

MJ-X provides an integrated visual workspace that reflects the assistant's internal cognitive state:
- **PyQt6 Native Canvas:** High-FPS, hardware-accelerated desktop overlay displaying live avatar states, transcription, and interactive cards.
- **FastAPI Web Dashboard:** Browser-accessible control center (`dashboard/server.py`) for system telemetry, memory exploration, and security audits.

---

## 2. DYNAMIC WIDGET REGISTRY & EVENT BUS

The `VisualHubController` and `WidgetRegistry` manage live workspace cards:
- **Widget Types:**
  - `status_card`: Live CPU, memory, and model connection latency.
  - `timeline`: Step-by-step autonomous agent action execution progress.
  - `metric_gauge`: Emotion valence/arousal, user WPM, and conversation cadence.
  - `memory_viewer`: Inspects recent episodic facts and user preferences.
- **Publish-Subscribe Dispatch:** UI subscribers receive immediate event callbacks when widgets update, eliminating polling.
