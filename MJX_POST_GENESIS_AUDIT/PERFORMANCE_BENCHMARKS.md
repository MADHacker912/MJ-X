# MJ-X POST-GENESIS AUDIT — 05: PERFORMANCE BENCHMARKS

**Audit Phase:** Phase 5 — Empirical Host Benchmarks & Resource Profiling  
**Host Platform:** Linux x86_64 (Intel ThinkPad / Ubuntu 24.04, 8GB RAM baseline)  
**Methodology:** Direct profiling via `/proc/self/status` (VmRSS) and `time.perf_counter()`  

---

## 1. EMPIRICAL BENCHMARK COMPARISON TABLE

| Benchmark Category | Genesis Claimed | Actual Measured Reality | Discrepancy / Root Cause |
|---|---|---|---|
| **Standalone Subsystem Import** | 242.0 ms | **311.7 ms** | Acceptable variance (+69.7 ms). |
| **Full Application Import (`main.py`)** | *Not Reported* | **2838.6 ms (2.84s)** | `main.py` loads PyQt6, OpenCV, PyAutoGUI, GenAI SDK. |
| **Standalone Subsystems RAM** | 38.3 MB | **26.7 MB** net (37.0 MB total) | Confirmed: standalone `mjx/` is extremely lightweight. |
| **Full Application Idle RAM (`main.py`)**| *Not Reported* | **190.5 MB VmRSS** | Real desktop app with GUI libraries requires ~190MB baseline. |
| **SQLite WAL Write Latency** | 0.96 ms / rec | **0.262 ms / rec** | Exceeds target SLA ($< 5\text{ ms}$). |
| **SQLite FTS5 Query Latency** | 2.82 ms / query | **1.068 ms / query** | Exceeds target SLA ($< 10\text{ ms}$). |
| **Child Process Spawn & Sanitize** | 14.2 ms | **16.1 ms** | Meets target SLA ($< 50\text{ ms}$). |
| **Coordinate Normalization** | 0.015 ms | **0.012 ms** | Pure arithmetic, negligible CPU overhead. |
| **Full Test Suite Runtime** | 7.27 s | **6.12 s** | 103 tests pass in 6.12 seconds on host CPU. |

---

## 2. LATENCY ANALYSIS & REAL-TIME INTERACTION

1. **Audio Streaming Latency (Gemini Live API):**
   - Direct WebSocket streaming over PCM16 24 kHz audio.
   - Network round-trip latency to Google servers: ~350–600ms depending on Internet connection.
   - Local audio processing (`apply_pcm16_settings`): 0.28ms per chunk (negligible).
2. **Database Throughput:**
   - SQLite WAL mode handles up to ~3,800 inserts per second on local SSD.
   - Zero lock contention between read queries and background backup threads.
3. **Desktop Memory Footprint:**
   - Cold startup: 190.5 MB RSS.
   - During active camera/screen capture: ~240–280 MB RSS peak.
   - Well within acceptable bounds for an 8GB RAM laptop profile.
