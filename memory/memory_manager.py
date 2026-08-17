"""Public and backward-compatible API for MJ's long-term memory engine."""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from typing import Any, Iterable

from .engine import MemoryEngine
from .models import CATEGORIES, MemoryRecord, normalize_category, normalize_key, utc_now


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_PATH = MEMORY_DIR / "long_term.json"  # legacy compatibility; new writes use category stores
_lock = threading.RLock()
_engine = MemoryEngine(MEMORY_DIR)


# Developer API requested by the application contract.
def loadMemory(category: str | None = None, include_archived: bool = False) -> list[dict[str, Any]]:
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
        record = _engine.add(
            memory.category, memory.key, memory.value, memory.confidence,
            memory.importance, memory.source, memory.expires_at,
        )
    elif isinstance(memory, dict):
        record = _engine.add(
            category or memory.get("category", "notes"),
            memory.get("key", "memory"), memory.get("value", ""),
            memory.get("confidence", 0.7), memory.get("importance", 5),
            memory.get("source", source), memory.get("expires_at"),
        )
    else:
        raise TypeError("memory must be a MemoryRecord or dictionary")
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
    return _engine.search(
        query=query, category=category, date_from=date_from, date_to=date_to,
        min_importance=min_importance, include_archived=include_archived,
        fuzzy=fuzzy, limit=limit, touch=True,
    )


def updateMemory(memory_id: str, **changes: Any) -> dict[str, Any] | None:
    record = _engine.update(memory_id, **changes)
    return record.to_dict() if record else None


def deleteMemory(memory_id: str) -> bool:
    return _engine.delete(memory_id)


def archiveMemory(memory_id: str) -> bool:
    return _engine.archive(memory_id)


def restoreMemory(memory_id: str) -> bool:
    return _engine.restore(memory_id)


def mergeMemory(memory_ids: Iterable[str], key: str | None = None) -> dict[str, Any] | None:
    record = _engine.merge(memory_ids, key)
    return record.to_dict() if record else None


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
    path = _engine.storage.backup(force=force)
    return str(path) if path else None


def rankMemory(memory: dict[str, Any] | MemoryRecord, query: str) -> float:
    record = memory if isinstance(memory, MemoryRecord) else MemoryRecord.from_dict(memory)
    from .models import normalize_text
    from .storage import _tokenize

    return round(_engine.rank(record, normalize_text(query), _tokenize(query)), 4)


def getRelevantMemory(message: str, limit: int = 12) -> list[dict[str, Any]]:
    return _engine.relevant(message, limit)


def learnFromConversation(user_message: str) -> list[dict[str, Any]]:
    return [record.to_dict() for record in _engine.learn(user_message)]


def cleanupMemory() -> dict[str, int]:
    return _engine.cleanup()


def verifyMemoryIntegrity() -> dict[str, str]:
    return _engine.storage.verify_integrity()


def load_state(key: str, default: Any = None) -> Any:
    return _engine.storage.load_state(key, default)


def save_state(key: str, value: Any) -> None:
    _engine.storage.save_state(key, value)


# Async counterparts use worker threads, keeping GUI and Gemini event loops responsive.
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


# Existing MJ compatibility API.
def load_memory() -> dict[str, Any]:
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
    return _engine.format_relevant_for_prompt(message, limit)


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
    _engine.add("conversation_summary", key, summary[:1200], 0.85, 6, source)


def pop_last_session() -> dict[str, Any] | None:
    records = _engine.storage.load_category("conversation_summary", include_archived=False)
    records = [record for record in records if not record.archived]
    if not records:
        return None
    latest = max(records, key=lambda record: record.created_at)
    _engine.archive(latest.id)
    language = latest.source.partition(":")[2] if latest.source.startswith("session_summary:") else ""
    return {"date": latest.created_at[:10], "summary": latest.value, "language": language}
