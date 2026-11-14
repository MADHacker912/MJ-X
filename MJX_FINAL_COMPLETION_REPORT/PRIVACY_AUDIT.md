# MJ-X SINGULARITY — 10 PRIVACY AUDIT

**Audit Scope:** Local-first data governance, zero unconsented telemetry, audio stream lifecycle, and memory confidentiality.  
**Auditor:** Antigravity AI Autonomous Security & Privacy Auditor  
**Status:** COMPLIANT WITH LOCAL-FIRST STANDARD

---

## 1. LOCAL-FIRST DATA GOVERNANCE DIRECTIVE

MJ-X operates under the strict principle that personal context, audio signals, conversation records, and knowledge graphs belong solely to the user and must remain on the local machine:

1. **Zero External Memory Storage:** No cloud database, Firebase, Supabase, or vector store is used for long-term memory. Canonical memories reside exclusively in local SQLite (`data/mjx_memory.db`).
2. **Local Full-Text Indexing:** Search queries and semantic relevance scoring run locally through SQLite FTS5 using BM25 ranking. No conversation contents are transmitted to third-party search APIs.
3. **Transient Audio Pipeline:** Microphone PCM audio streams directly over TLS WebSockets to the Gemini Live endpoint during active speech and is immediately discarded from memory. No audio waveforms are written to disk.
4. **Ephemerality of Vision Captures:** Screenshots and webcam captures taken for multimodal grounding are held as temporary in-memory byte buffers (`_pending_vision`) and cleared immediately after transmission.
5. **No Telemetry Phoning Home:** `EvolutionMetricsCollector` and `SystemMonitor` write exclusively to local process memory; zero diagnostic telemetry is broadcast over the internet.

---

## 2. DATA STORAGE INVENTORY

| Data Category | Storage Engine | Location on Disk | Encryption / Protection |
| :--- | :--- | :--- | :--- |
| **API Keys** | OS Keyring / AES-GCM | Platform Keyring / `config/.vault_manifest.json` | OS Protected / AES-256-GCM |
| **Long-Term Memory** | SQLite3 (FTS5) | `data/mjx_memory.db` | Local file permissions |
| **Conversations** | SQLite3 | `data/mjx_memory.db` | Local file permissions |
| **User Settings** | JSON | `memory/config.json` | Local file permissions |
| **Temporary Uploads** | Filesystem | `~/Downloads/MJ Uploads` or `uploads/` | Local file permissions |
| **Audio Frames** | In-Memory Queue | RAM only | Discarded after playback |
| **Screenshots** | In-Memory Buffer | RAM only | Discarded after transmission |

---

## 3. AUDIT VERIFICATION RESULTS

1. **Audio File Inspection:** Confirmed no `.wav`, `.pcm`, or `.mp3` recording files are created during live voice turns.
2. **Third-Party Network Traffic:** Only legitimate outbound traffic is the direct Gemini Live API WebSocket connection (`generativelanguage.googleapis.com`) and user-initiated web searches via DuckDuckGo.
3. **Localhost Restriction:** Confirmed dashboard server defaults to `127.0.0.1`, rejecting inbound remote connections unless specifically overridden by the user.
