"""Public and backward-compatible API for MJ's long-term memory engine with SQLite WAL unification."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Iterable

from .engine import MemoryEngine
from .models import CATEGORIES, MemoryRecord, normalize_category, normalize_key, utc_now
from mjx.memory import (
    DatabaseManager,
    MemoryRepository,
    MemoryItem,
    BackupManager,
    RecoveryManager,
    get_db_manager,
)


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_PATH = MEMORY_DIR / "long_term.json"  # legacy compatibility

_lock = threading.RLock()
_db_manager: DatabaseManager | None = None
_repo: MemoryRepository | None = None
_engine = MemoryEngine(MEMORY_DIR)


def get_repository() -> MemoryRepository | None:
    """Lazily initialize and return the canonical SQLite memory repository."""
    global _db_manager, _repo
    with _lock:
        if _repo is None:
            try:
                _db_manager = get_db_manager()
                _repo = MemoryRepository(_db_manager)
                # Auto-migrate legacy JSON files if SQLite database is brand new/empty
                try:
                    active = _repo.list_memories(limit=1)
                    if not active:
                        _repo.import_legacy_json_memories(MEMORY_DIR)
                except Exception as exc:
                    print(f"[MemoryManager] Note during initial migration: {exc}")
            except Exception as exc:
                print(f"[MemoryManager] SQLite repository init notice: {exc}")
        return _repo


def set_repository(repo: MemoryRepository | None) -> None:
    """Set or override the active repository (used for dependency injection and tests)."""
    global _repo
    with _lock:
        _repo = repo


def _memory_item_to_dict(item: MemoryItem) -> dict[str, Any]:
    """Convert MemoryItem to backward-compatible dictionary representation."""
    return {
        "id": item.id,
        "category": item.category,
        "key": item.key,
        "value": item.value,
        "confidence": float(item.confidence),
        "importance": int(item.importance),
        "source": item.source,
        "is_archived": bool(item.is_archived),
        "archived": bool(item.is_archived),
        "created_at": item.created_at or utc_now(),
        "updated_at": item.updated_at or utc_now(),
        "expires_at": item.expires_at,
        "deleted": bool(item.is_archived),
        "history": [],
    }


# ── Developer API ─────────────────────────────────────────────────────────────

def loadMemory(category: str | None = None, include_archived: bool = False) -> list[dict[str, Any]]:
    repo = get_repository()
    if repo:
        try:
            items = repo.list_memories(
                category=category,
                include_archived=include_archived,
                limit=10000,
            )
            return [_memory_item_to_dict(it) for it in items]
        except Exception as exc:
            print(f"[MemoryManager] SQLite loadMemory error ({exc}); using fallback engine.")

    if category:
        records = _engine.storage.load_category(category, include_archived=include_archived)
    else:
        records = _engine.storage.all_records(include_archived=include_archived)
    return [record.to_dict() for record in records]


def saveMemory(
    memory: MemoryRecord | dict[str, Any],
    category: str | None = None,
    source: str = "developer_api",
) -> dict[str, Any]:
    if isinstance(memory, MemoryRecord):
        cat = memory.category
        key = memory.key
        val = memory.value
        conf = memory.confidence
        imp = memory.importance
        src = memory.source or source
        m_id = memory.id
    elif isinstance(memory, dict):
        cat = category or memory.get("category", "notes")
        key = memory.get("key", "memory")
        val = memory.get("value", "")
        conf = memory.get("confidence", 0.7)
        imp = memory.get("importance", 5)
        src = memory.get("source", source)
        m_id = memory.get("id")
    else:
        raise TypeError("memory must be a MemoryRecord or dictionary")

    repo = get_repository()
    if repo:
        try:
            item = repo.save_memory(
                category=cat,
                key=key,
                value=str(val),
                confidence=float(conf),
                importance=int(imp),
                source=str(src),
                memory_id=m_id,
            )
            try:
                _engine.add(cat, key, val, conf, imp, src)
            except Exception:
                pass
            return _memory_item_to_dict(item)
        except Exception as exc:
            print(f"[MemoryManager] SQLite saveMemory error ({exc}); using fallback engine.")

    record = _engine.add(cat, key, val, conf, imp, src)
    return record.to_dict()


def searchMemory(
    query: str = "",
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_importance: int = 1,
    include_archived: bool = False,
    fuzzy: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if not query.strip():
        return loadMemory(category=category, include_archived=include_archived)[:limit]

    repo = get_repository()
    if repo:
        try:
            results = repo.search_engine.search_memories(
                query=query,
                category=category,
                limit=limit,
            )
            formatted = []
            for r in results:
                if int(r.get("importance", 5)) < min_importance:
                    continue
                formatted.append({
                    "id": r.get("id", ""),
                    "category": r.get("category", ""),
                    "key": r.get("key", ""),
                    "value": r.get("value", ""),
                    "confidence": float(r.get("confidence", 0.8)),
                    "importance": int(r.get("importance", 5)),
                    "source": r.get("source", "fts5_search"),
                    "created_at": r.get("created_at", utc_now()),
                    "updated_at": r.get("created_at", utc_now()),
                    "is_archived": False,
                    "archived": False,
                })
            return formatted
        except Exception as exc:
            print(f"[MemoryManager] SQLite searchMemory error ({exc}); using fallback search.")

    return _engine.search(
        query=query, category=category, date_from=date_from, date_to=date_to,
        min_importance=min_importance, include_archived=include_archived,
        fuzzy=fuzzy, limit=limit, touch=True,
    )


def updateMemory(memory_id: str, **changes: Any) -> dict[str, Any] | None:
    repo = get_repository()
    if repo:
        try:
            with repo.db.transaction() as conn:
                item = repo.get_memory(memory_id)
                if item:
                    val = str(changes.get("value", item.value))
                    conf = float(changes.get("confidence", item.confidence))
                    imp = int(changes.get("importance", item.importance))
                    src = str(changes.get("source", item.source))
                    key = str(changes.get("key", item.key))
                    cat = str(changes.get("category", item.category))

                    conn.execute(
                        """
                        UPDATE memories
                        SET value = ?, confidence = ?, importance = ?, source = ?, key = ?, category = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?;
                        """,
                        (val, conf, imp, src, key, cat, memory_id),
                    )
                    try:
                        conn.execute("DELETE FROM memories_fts WHERE memory_id = ?;", (memory_id,))
                        conn.execute(
                            "INSERT INTO memories_fts (memory_id, category, key, value) VALUES (?, ?, ?, ?);",
                            (memory_id, cat, key, val),
                        )
                    except Exception:
                        pass
                    updated = repo.get_memory(memory_id)
                    if updated:
                        return _memory_item_to_dict(updated)
        except Exception as exc:
            print(f"[MemoryManager] SQLite updateMemory error ({exc}); using fallback.")

    record = _engine.update(memory_id, **changes)
    return record.to_dict() if record else None


def deleteMemory(memory_id: str, hard_delete: bool = False) -> bool:
    repo = get_repository()
    if repo:
        try:
            item = repo.get_memory(memory_id)
            repo.delete_memory(memory_id, hard_delete=hard_delete)
            if item:
                try:
                    for r in _engine.storage.load_category(item.category, include_archived=True):
                        if r.key == item.key or r.id == memory_id:
                            _engine.delete(r.id)
                except Exception:
                    pass
        except Exception as exc:
            print(f"[MemoryManager] SQLite deleteMemory error: {exc}")
    return _engine.delete(memory_id)


def archiveMemory(memory_id: str) -> bool:
    repo = get_repository()
    if repo:
        try:
            repo.delete_memory(memory_id, hard_delete=False)
        except Exception as exc:
            print(f"[MemoryManager] SQLite archiveMemory error: {exc}")
    return _engine.archive(memory_id)


def restoreMemory(memory_id: str) -> bool:
    repo = get_repository()
    if repo:
        try:
            with repo.db.transaction() as conn:
                conn.execute(
                    "UPDATE memories SET is_archived = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                    (memory_id,),
                )
        except Exception as exc:
            print(f"[MemoryManager] SQLite restoreMemory error: {exc}")
    return _engine.restore(memory_id)


def mergeMemory(memory_ids: Iterable[str], key: str | None = None) -> dict[str, Any] | None:
    record = _engine.merge(memory_ids, key)
    if record:
        repo = get_repository()
        if repo:
            try:
                repo.save_memory(
                    category=record.category,
                    key=record.key,
                    value=record.value,
                    confidence=record.confidence,
                    importance=record.importance,
                    source="merge",
                    memory_id=record.id,
                )
            except Exception:
                pass
        return record.to_dict()
    return None


def summarizeConversation(
    conversation: str | Iterable[str],
    summarizer=None,
    save: bool = False,
    language: str = "",
) -> str:
    summary = _engine.summarize_conversation(conversation, summarizer)
    if save and summary:
        save_session_summary(summary, language)
    return summary


def compressMemory(category: str | None = None) -> dict[str, int]:
    return _engine.compress(category)


def backupMemory(force: bool = True) -> str | None:
    repo = get_repository()
    if repo:
        try:
            bm = BackupManager(repo.db)
            path = bm.create_backup()
            return str(path)
        except Exception as exc:
            print(f"[MemoryManager] SQLite backup error ({exc}); using fallback.")
    path = _engine.storage.backup(force=force)
    return str(path) if path else None


def rankMemory(memory: dict[str, Any] | MemoryRecord, query: str) -> float:
    record = memory if isinstance(memory, MemoryRecord) else MemoryRecord.from_dict(memory)
    from .models import normalize_text
    from .storage import _tokenize

    return round(_engine.rank(record, normalize_text(query), _tokenize(query)), 4)


def getRelevantMemory(message: str, limit: int = 12) -> list[dict[str, Any]]:
    repo = get_repository()
    if repo:
        try:
            results = repo.search_engine.search_memories(message, limit=limit)
            if results:
                return [
                    {
                        "id": r.get("id", ""),
                        "category": r.get("category", ""),
                        "key": r.get("key", ""),
                        "value": r.get("value", ""),
                        "confidence": float(r.get("confidence", 0.8)),
                        "importance": int(r.get("importance", 5)),
                        "source": r.get("source", "fts5"),
                    }
                    for r in results
                    if int(r.get("importance", 5)) >= 2
                ]
        except Exception as exc:
            print(f"[MemoryManager] SQLite getRelevantMemory error ({exc}); using fallback.")
    return _engine.relevant(message, limit)


def learnFromConversation(user_message: str) -> list[dict[str, Any]]:
    learned = []
    for rec in _engine.learn(user_message):
        d = saveMemory(rec)
        learned.append(d)
    return learned


def cleanupMemory() -> dict[str, int]:
    return _engine.cleanup()


def verifyMemoryIntegrity() -> dict[str, str]:
    res: dict[str, str] = {}
    repo = get_repository()
    if repo:
        try:
            ok, msg = repo.db.check_integrity()
            res["sqlite"] = "ok" if ok else f"error: {msg}"
        except Exception as exc:
            res["sqlite"] = f"exception: {exc}"
    try:
        json_res = _engine.storage.verify_integrity()
        res.update(json_res)
    except Exception:
        pass
    return res


def load_state(key: str, default: Any = None) -> Any:
    repo = get_repository()
    if repo:
        try:
            val = repo.get_user_profile(f"state:{key}")
            if val is not None:
                try:
                    return json.loads(val)
                except Exception:
                    return val
        except Exception as exc:
            print(f"[MemoryManager] SQLite load_state error: {exc}")
    return _engine.storage.load_state(key, default)


def save_state(key: str, value: Any) -> None:
    repo = get_repository()
    if repo:
        try:
            json_val = json.dumps(value) if not isinstance(value, str) else value
            repo.set_user_profile(f"state:{key}", json_val)
        except Exception as exc:
            print(f"[MemoryManager] SQLite save_state error: {exc}")
    try:
        _engine.storage.save_state(key, value)
    except Exception:
        pass


# ── Async Counterparts ────────────────────────────────────────────────────────

async def loadMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(loadMemory, *args, **kwargs)


async def saveMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(saveMemory, *args, **kwargs)


async def searchMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(searchMemory, *args, **kwargs)


async def getRelevantMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(getRelevantMemory, *args, **kwargs)


async def updateMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(updateMemory, *args, **kwargs)


async def deleteMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(deleteMemory, *args, **kwargs)


async def archiveMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(archiveMemory, *args, **kwargs)


async def restoreMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(restoreMemory, *args, **kwargs)


async def mergeMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(mergeMemory, *args, **kwargs)


async def summarizeConversationAsync(*args, **kwargs):
    return await asyncio.to_thread(summarizeConversation, *args, **kwargs)


async def compressMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(compressMemory, *args, **kwargs)


async def backupMemoryAsync(*args, **kwargs):
    return await asyncio.to_thread(backupMemory, *args, **kwargs)


# ── Existing MJ Compatibility API ─────────────────────────────────────────────

def load_memory() -> dict[str, Any]:
    repo = get_repository()
    if repo:
        try:
            items = repo.list_memories(include_archived=False, limit=10000)
            result: dict[str, Any] = {category: {} for category in CATEGORIES}
            for item in items:
                cat = item.category
                if cat not in result:
                    result[cat] = {}
                result[cat][item.key] = {
                    "id": item.id,
                    "value": item.value,
                    "confidence": item.confidence,
                    "importance": item.importance,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                    "source": item.source,
                }
            result["monitors"] = load_state("monitors", {})
            return result
        except Exception as exc:
            print(f"[MemoryManager] SQLite load_memory error ({exc}); using legacy view.")
    return _engine.legacy_view()


def save_memory(memory: dict[str, Any]) -> None:
    if not isinstance(memory, dict):
        raise TypeError("memory must be a dictionary")
    monitors = memory.get("monitors")
    if isinstance(monitors, dict):
        save_state("monitors", monitors)
    for category, items in memory.items():
        if category == "monitors" or not isinstance(items, dict):
            continue
        for key, entry in items.items():
            value = entry.get("value") if isinstance(entry, dict) else entry
            if value not in (None, ""):
                saveMemory({
                    "category": category,
                    "key": key,
                    "value": value,
                    "confidence": entry.get("confidence", 0.75) if isinstance(entry, dict) else 0.75,
                    "importance": entry.get("importance", 5) if isinstance(entry, dict) else 5,
                    "source": entry.get("source", "compatibility_api") if isinstance(entry, dict) else "compatibility_api",
                })


def update_memory(memory_update: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(memory_update, dict):
        return load_memory()
    for category, items in memory_update.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            value = entry.get("value") if isinstance(entry, dict) else entry
            if value in (None, ""):
                continue
            saveMemory({
                "category": category,
                "key": key,
                "value": value,
                "confidence": entry.get("confidence", 0.8) if isinstance(entry, dict) else 0.8,
                "importance": entry.get("importance", 6) if isinstance(entry, dict) else 6,
                "source": entry.get("source", "assistant_tool") if isinstance(entry, dict) else "assistant_tool",
            })
    return load_memory()


def format_memory_for_prompt(memory: dict[str, Any] | None = None, max_items: int = 24) -> str:
    memory = memory or load_memory()
    entries: list[tuple[int, float, str, str, str]] = []
    for category in CATEGORIES:
        items = memory.get(category, {})
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            if isinstance(entry, dict):
                value = entry.get("value")
                importance = int(entry.get("importance", 5))
                confidence = float(entry.get("confidence", 0.7))
            else:
                value, importance, confidence = entry, 5, 0.7
            if value:
                entries.append((importance, confidence, category, key, str(value)))
    entries.sort(reverse=True)
    if not entries:
        return ""
    lines = ["[LONG-TERM MEMORY - use naturally; never recite as a list]"]
    for _, _, category, key, value in entries[:max_items]:
        lines.append(f"- {category}/{key}: {value}")
    return "\n".join(lines)[:5000] + "\n"


def format_relevant_memory_for_prompt(message: str, limit: int = 12) -> str:
    memories = getRelevantMemory(message, limit)
    if not memories:
        return ""
    lines = ["[RELEVANT LONG-TERM MEMORY - use only when helpful]"]
    for memory in memories:
        lines.append(f"- {memory['category']}/{memory['key']}: {memory['value']}")
    return "\n".join(lines)


def remember(key: str, value: str, category: str = "notes") -> str:
    record = saveMemory({
        "category": category, "key": key, "value": value,
        "confidence": 0.9, "importance": 7, "source": "explicit_remember",
    })
    return f"Remembered: {record['category']}/{record['key']} = {record['value']}"


def forget(key: str, category: str = "notes") -> str:
    category = normalize_category(category)
    key = normalize_key(key)
    matches = [record for record in loadMemory(category) if record["key"] == key and not record.get("archived")]
    if not matches:
        return f"Not found: {category}/{key}"
    for record in matches:
        archiveMemory(record["id"])
    return f"Forgotten: {category}/{key}"


forget_memory = forget


def save_session_summary(summary: str, language: str = "") -> None:
    summary = str(summary or "").strip()
    if not summary:
        return
    source = f"session_summary:{language or 'unknown'}"
    key = f"session_{utc_now().replace(':', '').replace('+', '_')}"
    repo = get_repository()
    if repo:
        try:
            repo.save_memory(
                category="conversation_summary",
                key=key,
                value=summary[:1200],
                confidence=0.85,
                importance=6,
                source=source,
            )
        except Exception as exc:
            print(f"[MemoryManager] SQLite save_session_summary error: {exc}")
    try:
        _engine.add("conversation_summary", key, summary[:1200], 0.85, 6, source)
    except Exception:
        pass


def pop_last_session() -> dict[str, Any] | None:
    repo = get_repository()
    if repo:
        try:
            items = repo.list_memories(category="conversation_summary", include_archived=False, limit=100)
            if not items:
                return None
            latest = max(items, key=lambda it: it.created_at or "")
            repo.delete_memory(latest.id, hard_delete=False)
            language = latest.source.partition(":")[2] if latest.source.startswith("session_summary:") else ""
            date_str = (latest.created_at or utc_now())[:10]
            try:
                for rec in _engine.storage.load_category("conversation_summary", include_archived=False):
                    _engine.archive(rec.id)
            except Exception:
                pass
            return {"date": date_str, "summary": latest.value, "language": language}
        except Exception as exc:
            print(f"[MemoryManager] SQLite pop_last_session error: {exc}")

    records = _engine.storage.load_category("conversation_summary", include_archived=False)
    records = [record for record in records if not record.archived]
    if not records:
        return None
    latest = max(records, key=lambda record: record.created_at)
    _engine.archive(latest.id)
    language = latest.source.partition(":")[2] if latest.source.startswith("session_summary:") else ""
    return {"date": latest.created_at[:10], "summary": latest.value, "language": language}


# ── Conversation Persistence APIs ─────────────────────────────────────────────

def start_conversation(title: str = "New Conversation", conv_id: str | None = None) -> str:
    """Start and persist a conversation session."""
    repo = get_repository()
    if repo:
        try:
            return repo.start_conversation(title=title, conv_id=conv_id)
        except Exception as exc:
            print(f"[MemoryManager] start_conversation error: {exc}")
    return conv_id or str(uuid.uuid4())


def add_conversation_message(conversation_id: str, role: str, content: str) -> str:
    """Log an exchange turn into conversations/messages and index into messages_fts."""
    repo = get_repository()
    if repo:
        try:
            return repo.add_message(conversation_id, role, content)
        except Exception as exc:
            print(f"[MemoryManager] add_conversation_message error: {exc}")
    return str(uuid.uuid4())


def get_conversation_messages(conversation_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve message history for a conversation."""
    repo = get_repository()
    if repo:
        try:
            return repo.get_messages(conversation_id, limit)
        except Exception as exc:
            print(f"[MemoryManager] get_conversation_messages error: {exc}")
    return []


def update_conversation_summary(conversation_id: str, summary: str) -> bool:
    """Update conversation summary in database."""
    repo = get_repository()
    if repo:
        try:
            return repo.update_conversation_summary(conversation_id, summary)
        except Exception as exc:
            print(f"[MemoryManager] update_conversation_summary error: {exc}")
    return False
