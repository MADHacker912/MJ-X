# MJ-X SINGULARITY — 13 KNOWN LIMITATIONS

**Scope:** Honest architectural and operational limitations of the current unified MJ-X desktop runtime.  
**Policy:** Zero fabricated claims; all technical constraints documented explicitly.

---

## 1. INTENT CLASSIFICATION LIMITATIONS (OMNIBRAIN)
- **Pattern-Based Matching:** `IntentClassifier` relies on regex keyword heuristics and rule matrices rather than an onboard neural sentence transformer. Complex, grammatically ambiguous, or ironic prompts may occasionally fall back to standard `conversational` handling.
- **Language Boundaries:** Dual-mode classifier accurately detects English and Hindi-Latin (Hinglish). Other regional Indian languages (Tamil, Telugu, Bengali) are not currently classified deterministically.

## 2. DESKTOP AUTOMATION BOUNDARIES (GHOST)
- **Permission Pre-requisite:** Autonomous OS input control is locked by default. Without manual grants (`PermissionCategory.OS_INPUT_CONTROL`), GHOST will veto action steps and fall back to the safe sandboxed generator.
- **Wayland Display Limitations:** On Linux running native Wayland sessions (e.g., GNOME on Ubuntu 22.04+), PyAutoGUI screen coordinate injections may be restricted by the compositor unless XWayland compatibility or portal permissions are active.

## 3. SKILL REGISTRY LIFECYCLE (NEXUS)
- **In-Memory Registry:** Registered skills reside in process memory. Dynamic skills registered via API must be re-registered on application restart unless loaded from configured manifest directories.
- **Python-Only In-Process Execution:** While MCP schema mappings exist, direct foreign process RPC calls (e.g., stdio MCP clients) require external helper wrappers.

## 4. COMPANION STATE PERSISTENCE (AURORA)
- **Session Ephemerality:** Paired companion tokens and mobile telemetry states are stored in process RAM (`_authenticated_tokens`, `_states`). Restarting the MJ-X desktop application terminates active pairing sessions, requiring a re-handshake from the mobile companion.

## 5. TELEMETRY PERSISTENCE (EVOLVE)
- **Volatile Rolling Window:** `EvolutionMetricsCollector` holds up to 500 runtime samples in memory. Long-term statistical aggregation across months requires persistent SQLite storage (targeted for future P3 expansion).

## 6. EXTERNAL DEPENDENCIES & ENVIRONMENT CONSTRAINTS
- **Network Dependency for Live Voice:** While canonical memories and intelligence planning run locally, natural conversational voice synthesis relies on active internet connectivity to Google's Gemini Live API.
- **Port Binding:** Local dashboard requires access to port 8000; conflicts must be configured via `MJ_DASHBOARD_PORT`.
