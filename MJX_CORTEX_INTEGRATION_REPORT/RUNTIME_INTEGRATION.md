# MJ-X CORTEX RUNTIME UNIFICATION — RUNTIME INTEGRATION REPORT

**Subsystem:** Cortex Runtime & Facade Layer  
**Target Files:** `memory/memory_manager.py`, `main.py`, `mjx/memory/repository.py`  
**Status:** COMPLETE & PRODUCTION-READY  
**Date:** November 13, 2026  

---

## 1. Runtime Wiring Architecture

To prevent breaking existing modules and action scripts, `memory/memory_manager.py` was retained as the universal entry point while completely redirecting internal operations to `mjx.memory.MemoryRepository`.

```mermaid
flowchart TD
    subgraph Callers
        M[main.py]
        U[ui.py]
        E[emotion/memory.py]
        P[personality/preferences.py]
        A[actions/proactive.py]
    end

    subgraph Facade["memory/memory_manager.py"]
        FM[loadMemory / saveMemory / searchMemory / updateMemory / deleteMemory / pop_last_session / load_memory]
    end

    subgraph Canonical["mjx.memory Engine (Primary)"]
        MR[MemoryRepository]
        DM[DatabaseManager (WAL + Busy Timeout)]
        FTS[FTS5 Search Engine + Hinglish Tokenizer]
    end

    subgraph Fallback["Legacy Engine (Fail-Closed)"]
        ME[MemoryEngine / JsonMemoryStorage]
    end

    Callers --> FM
    FM -->|Primary Route| MR
    MR --> DM
    MR --> FTS
    FM -.->|If SQLite Unavailable| ME
```

---

## 2. API Facade Implementation Details

Every function in `memory/memory_manager.py` was updated with fail-closed SQLite delegating logic:

### 2.1 `loadMemory(category=None, include_archived=False) -> list[dict]`
- Queries `repo.list_memories(category, include_archived, limit=10000)`.
- Translates `MemoryItem` to dictionary representation with both `is_archived` and `archived` attributes.
- On exception: logs notice and transparently returns fallback from `_engine.storage`.

### 2.2 `saveMemory(memory, category=None, source="developer_api") -> dict`
- Accepts either `MemoryRecord` dataclass or standard dictionary.
- Saves record atomically into SQLite `memories` table with upsert semantics.
- Synchronizes changes to `memories_fts` index within the same transaction.
- Non-blockingly mirrors to fallback memory engine.

### 2.3 `searchMemory(query="", category=None, limit=50) -> list[dict]`
- Uses `repo.search_engine.search_memories(query, category, limit)`.
- Evaluates FTS5 match expression with BM25 ranking and Hinglish token normalization.
- Falls back to LIKE pattern matching if FTS5 syntax fails.

### 2.4 `updateMemory(memory_id, **changes) -> dict | None`
- Updates fields (`value`, `confidence`, `importance`, `source`, `key`, `category`) inside a transaction.
- Automatically refreshes the corresponding `memories_fts` virtual table record.

### 2.5 `deleteMemory(memory_id, hard_delete=False) -> bool`
- Soft-delete: Sets `is_archived = 1` and updates timestamp.
- Hard-delete: Completely removes row from `memories` and deletes from `memories_fts`.

### 2.6 `load_memory() -> dict[str, Any]`
- Rebuilds the nested dictionary structure `{category: {key: {id, value, confidence, importance, ...}}}` expected by `main.py` prompt generators (`format_memory_for_prompt`).
- Injects persistent monitors from `user_profile` table.

### 2.7 `pop_last_session() -> dict | None`
- Retrieves the latest session summary from `category = 'conversation_summary'`.
- Atomically marks the summary archived in SQLite so it is never repeated across sessions.
- Cleans the fallback engine copy to maintain state synchronization.

---

## 3. Conversation History Tracking in `main.py`

`main.py` was updated to log live dialogue sessions:
- On startup: Initialized `self._conversation_id = start_conversation("Live Voice Session")`.
- On user input (typed or speech): Calls `add_conversation_message(self._conversation_id, "user", text)`.
- On assistant response: Calls `add_conversation_message(self._conversation_id, "assistant", full_out)`.
- On session completion: Calls `update_conversation_summary(self._conversation_id, summary)`.

All turns are indexed into `messages_fts` in real time, making past conversation history instantly searchable.
