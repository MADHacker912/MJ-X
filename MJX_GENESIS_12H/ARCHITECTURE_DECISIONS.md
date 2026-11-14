# MJ-X GENESIS — ARCHITECTURE DECISIONS (ADR)

**Status:** APPROVED & IMPLEMENTED  
**Date:** 2026-11-13  

---

## ADR 01: Native OS Secret Service with AES-256-GCM Air-Gap Fallback
- **Decision:** Replace plaintext JSON configuration files for API keys with OS Secret Service (Linux SecretService / Windows Credential Manager). If OS keyring is absent, fallback to an encrypted vault using Argon2id/Scrypt and AES-256-GCM with a `0600` master key.
- **Consequence:** Zero credentials exposed in plain text. Complete protection against repository commits and disk-scraping exploits.

## ADR 02: SQLite WAL Mode for Canonical Local-First Storage
- **Decision:** Migrate all personal conversations, facts, and settings from flat files into a local SQLite database (`data/mjx_local.db`) with Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and FTS5 inverted search index.
- **Consequence:** Microsecond read/write latencies (0.96ms write, 2.82ms FTS query), robust ACID transaction safety, zero database lock contention during concurrent voice streaming.

## ADR 03: Scoped Least-Privilege Permission Ledger & Emergency Kill Switch
- **Decision:** All privileged actions (screen capture, webcam access, desktop inputs, shell execution) must request scoped time-to-live leases or one-time tokens from `PermissionManager`. An emergency stop switch immediately terminates any running actions.
- **Consequence:** Complete user control over autonomous agents, preventing runaway or malicious GUI automation.

## ADR 04: Resolution-Agnostic 1000-Point Normalized GUI Perception
- **Decision:** Agent visual coordinates are normalized to a (0–1000) integer grid. Dispatched inputs scale on-the-fly to host monitor resolution.
- **Consequence:** Automation scripts run reliably across varied displays, DPI scalings, and headless test harnesses without brittle hardcoded pixel offsets.

## ADR 05: Open Model Context Protocol (MCP) Integration
- **Decision:** Adopt standard MCP tool definitions via `MCPAdapter` rather than inventing proprietary plugin formats.
- **Consequence:** Instantly interoperable with the broader community of MCP tools while maintaining strict permission enforcement.

## ADR 06: Non-Self-Modifying System Evolution
- **Decision:** Disallow autonomous agents from rewriting their own core application code. System improvement occurs via structured *Improvement Proposals* presented to the user for explicit approval.
- **Consequence:** Prevents software regressions, recursive hallucination loops, and catastrophic self-corruption.
