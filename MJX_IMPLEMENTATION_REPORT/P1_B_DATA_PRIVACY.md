# MJ-X IMPLEMENTATION REPORT: P1-B DATA PRIVACY AND STORAGE BOUNDARIES

**Status:** COMPLETE & DOCUMENTED  
**Phase:** P1-B Data Privacy and Storage Boundaries  
**Date:** 2026-11-13  

---

## 1. DATA CLASSIFICATION AND LOCAL-FIRST BOUNDARIES

MJ-X establishes a strict architectural boundary between local-first personal storage and transient cloud inference:

```
┌────────────────────────────────────────────────────────┐
│               LOCAL DEVICE ONLY (DEFAULT)              │
├────────────────────────────────────────────────────────┤
│ • Canonical SQLite Database (data/mjx_local.db)       │
│ • Long-term Memories, Preferences, Habits, Facts       │
│ • Full Conversation History & Message Transcripts      │
│ • User Profile & Identity Settings                     │
│ • Security Credentials (OS Keyring / Encrypted Vault)  │
│ • Permission Audit Trail (logs/permission_audit.jsonl) │
│ • Saved Photos & Local Screen Captures (Photos/MJ)     │
│ • Local Backups (data/backups/mjx_backup_*.db)         │
└────────────────────────────────────────────────────────┘
                           │
       [Permission Gate: Explicit User Consent]
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             TRANSIENT CLOUD PROCESSING ONLY            │
├────────────────────────────────────────────────────────┤
│ • Google Gemini Live WebSocket (Bidirectional Audio)   │
│ • Google Gemini Multimodal Inference (Screen/Camera)   │
│ • ElevenLabs TTS (When explicitly enabled by user)     │
│ • DuckDuckGo / Google Search (Web search tool)         │
└────────────────────────────────────────────────────────┘
```

---

## 2. DATA TRANSMISSION INVENTORY

| Data Type | External Destination | Purpose | Local Retention | User Disabling Control |
|---|---|---|---|---|
| **Voice Audio Stream** (PCM 16kHz) | Google Gemini Live API | Real-time speech understanding and response | Transcripts stored in local SQLite; raw audio not permanently retained on disk | Mute microphone or sleep assistant (`set_state("SLEEPING")`) |
| **Screen Captures** (PNG/JPEG) | Google Gemini Multimodal API | Vision understanding of user desktop | Stored locally only if explicitly saved; memory buffer dropped after turn | Revoke `SCREEN_CAPTURE` permission; close vision window |
| **Webcam Frames** (JPEG) | Google Gemini Multimodal API | Physical world perception & photo capture | Saved to `Photos/MJ` locally | Revoke `CAMERA_ACCESS` permission; disconnect webcam |
| **Search Queries** | DuckDuckGo / Google Search | Live information retrieval | Query saved in conversation log | Disable web search tool |
| **TTS Text** | EdgeTTS / ElevenLabs (optional) | Audio synthesis | Audio stream cached in temp RAM | Select local Kokoro TTS engine in settings |

---

## 3. HONEST PRIVACY DISCLOSURE

> [!IMPORTANT]
> **No End-to-End Privacy for Cloud LLMs:**  
> When voice audio, screen frames, or user prompts are transmitted to Google Gemini Live API or external cloud providers, they are processed under the respective provider's terms and privacy policies. MJ-X guarantees that **canonical personal memory and databases never leave the device**, but inference requests transmitted over the network are subject to cloud provider transport encryption (TLS 1.3).
