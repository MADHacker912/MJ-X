"""Data contracts and normalization helpers for MJ long-term memory."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


CATEGORIES = (
    "identity",
    "preferences",
    "personality",
    "skills",
    "projects",
    "goals",
    "relationships",
    "devices",
    "locations",
    "habits",
    "schedule",
    "notes",
    "reminders",
    "conversation_summary",
    "semantic_memory",
    "episodic_memory",
    "facts",
    "achievements",
    "education",
    "work",
)

CATEGORY_FILES = {category: f"{category}.json" for category in CATEGORIES}
ALIASES = {
    "conversation summaries": "conversation_summary",
    "conversation_summaries": "conversation_summary",
    "sessions": "conversation_summary",
    "semantic memory": "semantic_memory",
    "episodic memory": "episodic_memory",
    "wishes": "goals",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_category(category: str) -> str:
    value = re.sub(r"\s+", "_", str(category or "notes").strip().lower())
    value = ALIASES.get(value, value)
    return value if value in CATEGORIES else "notes"


def normalize_key(key: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")
    return clean[:120] or "memory"


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def clamp_float(value: Any, low: float, high: float, default: float) -> float:
    try:
        return round(max(low, min(high, float(value))), 4)
    except (TypeError, ValueError):
        return default


def clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class MemoryRecord:
    id: str
    category: str
    key: str
    value: str
    confidence: float
    importance: int
    created_at: str
    updated_at: str
    source: str
    last_accessed: str
    archived: bool = False
    archived_at: str | None = None
    deleted: bool = False
    deleted_at: str | None = None
    expires_at: str | None = None
    access_count: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        category: str,
        key: str,
        value: Any,
        confidence: float = 0.7,
        importance: int = 5,
        source: str = "conversation",
        expires_at: str | None = None,
    ) -> "MemoryRecord":
        now = utc_now()
        return cls(
            id=uuid.uuid4().hex,
            category=normalize_category(category),
            key=normalize_key(key),
            value=str(value).strip(),
            confidence=clamp_float(confidence, 0.0, 1.0, 0.7),
            importance=clamp_int(importance, 1, 10, 5),
            created_at=now,
            updated_at=now,
            source=str(source or "unknown")[:120],
            last_accessed=now,
            expires_at=expires_at,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        required = {
            "id", "category", "key", "value", "confidence", "importance",
            "created_at", "updated_at", "source", "last_accessed",
        }
        missing = required.difference(data)
        if missing:
            raise ValueError(f"Memory record missing fields: {sorted(missing)}")
        return cls(
            id=str(data["id"]),
            category=normalize_category(data["category"]),
            key=normalize_key(data["key"]),
            value=str(data["value"]),
            confidence=clamp_float(data["confidence"], 0.0, 1.0, 0.7),
            importance=clamp_int(data["importance"], 1, 10, 5),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            source=str(data["source"]),
            last_accessed=str(data["last_accessed"]),
            archived=bool(data.get("archived", False)),
            archived_at=data.get("archived_at"),
            deleted=bool(data.get("deleted", False)),
            deleted_at=data.get("deleted_at"),
            expires_at=data.get("expires_at"),
            access_count=max(0, int(data.get("access_count", 0))),
            history=list(data.get("history", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def add_history(self, action: str, **details: Any) -> None:
        self.history.append({"at": utc_now(), "action": action, **details})
        if len(self.history) > 100:
            self.history = self.history[-100:]

    def touch(self) -> None:
        self.last_accessed = utc_now()
        self.access_count += 1
