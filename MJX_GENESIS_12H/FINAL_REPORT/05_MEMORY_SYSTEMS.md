# MJ-X GENESIS FINAL REPORT — 05: MEMORY SYSTEMS

**Subsystem:** Local-First SQLite-WAL Architecture & Hybrid Retrieval (Project CORTEX / P1)  
**Package:** `mjx.memory`  

---

## 1. STORAGE ARCHITECTURE & WAL CONCURRENCY

MJ-X completely removes legacy reliance on unindexed flat JSON files for long-term memory.
- **Engine:** SQLite 3.46.1 with write-ahead logging (`PRAGMA journal_mode = WAL`).
- **Pragmas Configured:**
  - `PRAGMA synchronous = NORMAL;` (optimal SSD write durability without latency penalties).
  - `PRAGMA foreign_keys = ON;` (relational integrity between conversations, turns, and entities).
  - `PRAGMA busy_timeout = 5000;` (prevents database locking during concurrent background threads).

---

## 2. RELATIONAL SCHEMA & MIGRATIONS

The local database (`data/mjx_local.db`) implements structured relational tables managed by `SchemaMigrator`:
1. `schema_migrations`: Version tracking and idempotency verification.
2. `conversations`: Sessions, titles, and timestamp boundaries.
3. `messages`: Conversational turns, roles, tokens, and emotion labels.
4. `memories`: Fact key-value storage, confidence ratings, categories (`personal`, `work`, `preference`), and source references.
5. `user_profile`: Canonical key-value settings, names, and preferences.
6. `memory_fts`: Virtual FTS5 table indexed on `key`, `value`, and `category` with Porter stemming and Hinglish tokenization.

---

## 3. FULL-TEXT SEARCH & HINGLISH EXPANSION

The `HinglishNormalizer` tokenizes blended South Asian terminology:
- Normalizes spelling variations: *"bhot"* $\rightarrow$ *"bohot"*, *"achha"* $\rightarrow$ *"accha"*, *"plz"* $\rightarrow$ *"please"*.
- Enables BM25 ranked queries across conversations and memory facts in under 3 milliseconds on local CPU.

---

## 4. BACKUP, INTEGRITY & AIR-GAPPED RECOVERY

- **Point-in-Time Online Backups:** `LocalBackupManager` executes non-blocking SQLite online backup API (`sqlite3_backup`).
- **Cryptographic Hash Verification:** SHA-256 integrity digests stored in backup metadata manifests.
- **Isolated Test Restore:** Automated restore testing runs against temporary sandbox databases before certifying backup health.
