# MJ-X SINGULARITY — 06 MIRROR IMPLEMENTATION

**Subsystem:** Project MIRROR / CORTEX Unified Local-First Memory Subsystem  
**Implementation Package:** `mjx/memory/`, `memory/`  
**Runtime Integration:** `memory/memory_manager.py`, `main.py` (`MJLive._send_user_text`, `MJLive._execute_tool`)

---

## 1. SUBSYSTEM RESPONSIBILITIES

Project MIRROR (built directly atop the unified P1 CORTEX foundation) manages the local-first contextual reflection and persistent knowledge graph of the user:

1. **Single Source of Truth:** Replaces legacy, scattered, competing JSON files with an ACID-compliant SQLite3 repository (`data/mjx_memory.db`).
2. **Profile & Knowledge Graph:** Stores personal preferences, relationship traits, learned facts, project paths, and interaction patterns indexed by `category`, `key`, `value`, `confidence`, and `importance`.
3. **Full-Text BM25 Search:** Operates an SQLite FTS5 index (`memories_fts`) with language-aware transliteration normalization, enabling rapid retrieval of relevant memories based on conversational queries.
4. **Conversation Session Management:** Tracks active conversation IDs, individual user and assistant turns, and periodic conversational summaries.
5. **Prompt Injection & Relevance Scoring:** Synthesizes the top-K relevant memories into the prompt context for Gemini Live without polluting context windows or leaking confidential tokens.

---

## 2. CODE ARTIFACTS & CORE CLASSES

- `mjx/memory/repository.py` — `MemoryRepository`
- `mjx/memory/db.py` — `DatabaseManager` (schema migration, connection pooling, VACUUM)
- `mjx/memory/search.py` — `MemorySearchEngine` (FTS5 BM25 ranked queries)
- `mjx/memory/models.py` — `MemoryRecord`, `ConversationRecord`, `TurnRecord`
- `memory/memory_manager.py` — High-level interface bridge (`get_repository()`, `update_memory()`, `searchMemory()`, `format_relevant_memory_for_prompt()`)

---

## 3. INTEGRATION IN LIVE RUNTIME

In `memory/memory_manager.py`:
- `get_repository()` provides the shared singleton instance of `MemoryRepository`.
- All legacy functions (`load_memory`, `update_memory`, `searchMemory`, `add_conversation_message`) write directly to the SQLite tables.

In `main.py`:
```python
# Shared repository passed to OMNIBRAIN
self.memory_repo = get_repository()
self.brain = IntelligenceBrain(memory_repo=self.memory_repo)

# Tool handling for memory operations in _execute_tool:
if name == "save_memory":
    category = args.get("category", "notes")
    key      = args.get("key", "")
    value    = args.get("value", "")
    if key and value:
        update_memory({category: {key: {
            "value": value,
            "confidence": args.get("confidence", 0.85),
            "importance": args.get("importance", 7),
            "source": "gemini_tool",
        }}})
```

---

## 4. TEST VERIFICATION EVIDENCE

Integrated in `tests/test_cortex_integration.py` and `tests/test_singularity_integration.py`:
- 14/14 P1 Cortex integration tests passing.
- Verified 0 data loss during JSON-to-SQLite schema migrations.
- Full-text search and BM25 relevance verified with Hinglish query variations.
- Verified prompt formatting injects relevant memories while respecting maximum token limits.
