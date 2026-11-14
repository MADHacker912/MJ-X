"""
mjx.memory.repository — Typed SQLite Repository with Parameterized Queries & Legacy Importer.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from .database import DatabaseManager, get_db_manager
from .migrations import MigrationManager
from .search import MemorySearchEngine


@dataclass
class MemoryItem:
    id: str
    category: str
    key: str
    value: str
    confidence: float = 0.8
    importance: int = 5
    source: str = "direct_conversation"
    is_archived: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None


class MemoryRepository:
    """Canonical local SQLite storage repository for memories, conversations, and user data."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()
        # Ensure migrations are applied
        MigrationManager(self.db).apply_all_migrations()
        self.search_engine = MemorySearchEngine(self.db)

    # ── Memory CRUD ──────────────────────────────────────────────────────────

    def save_memory(
        self,
        category: str,
        key: str,
        value: str,
        confidence: float = 0.8,
        importance: int = 5,
        source: str = "direct_conversation",
        tags: Optional[List[str]] = None,
        memory_id: Optional[str] = None,
    ) -> MemoryItem:
        """Insert or update a canonical memory record with FTS synchronization."""
        m_id = memory_id or str(uuid.uuid4())
        norm_cat = category.strip().lower()
        norm_key = key.strip().lower()
        clean_val = value.strip()

        with self.db.transaction() as conn:
            # Check existing key in category
            cursor = conn.execute(
                "SELECT id FROM memories WHERE category = ? AND key = ?;",
                (norm_cat, norm_key),
            )
            existing = cursor.fetchone()

            if existing:
                m_id = existing["id"]
                conn.execute(
                    """
                    UPDATE memories
                    SET value = ?, confidence = ?, importance = ?, source = ?, updated_at = CURRENT_TIMESTAMP, is_archived = 0
                    WHERE id = ?;
                    """,
                    (clean_val, confidence, importance, source, m_id),
                )
                # Update FTS
                try:
                    conn.execute("DELETE FROM memories_fts WHERE memory_id = ?;", (m_id,))
                    conn.execute(
                        "INSERT INTO memories_fts (memory_id, category, key, value) VALUES (?, ?, ?, ?);",
                        (m_id, norm_cat, norm_key, clean_val),
                    )
                except Exception:
                    pass
            else:
                conn.execute(
                    """
                    INSERT INTO memories (id, category, key, value, confidence, importance, source, is_archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0);
                    """,
                    (m_id, norm_cat, norm_key, clean_val, confidence, importance, source),
                )
                try:
                    conn.execute(
                        "INSERT INTO memories_fts (memory_id, category, key, value) VALUES (?, ?, ?, ?);",
                        (m_id, norm_cat, norm_key, clean_val),
                    )
                except Exception:
                    pass

            # Manage tags
            if tags:
                for tag in tags:
                    conn.execute(
                        "INSERT OR IGNORE INTO tags (memory_id, tag) VALUES (?, ?);",
                        (m_id, tag.strip().lower()),
                    )

        return MemoryItem(
            id=m_id,
            category=norm_cat,
            key=norm_key,
            value=clean_val,
            confidence=confidence,
            importance=importance,
            source=source,
        )

    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """Fetch memory item by ID."""
        conn = self.db.get_connection()
        cursor = conn.execute(
            "SELECT * FROM memories WHERE id = ? AND is_archived = 0;",
            (memory_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return MemoryItem(
            id=row["id"],
            category=row["category"],
            key=row["key"],
            value=row["value"],
            confidence=row["confidence"],
            importance=row["importance"],
            source=row["source"],
            is_archived=bool(row["is_archived"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_memories(
        self,
        category: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 100,
    ) -> List[MemoryItem]:
        """List stored memories with optional category filter."""
        conn = self.db.get_connection()
        sql = "SELECT * FROM memories WHERE 1=1"
        params: list = []

        if not include_archived:
            sql += " AND is_archived = 0"
        if category:
            sql += " AND category = ?"
            params.append(category.strip().lower())

        sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?;"
        params.append(limit)

        cursor = conn.execute(sql, params)
        return [
            MemoryItem(
                id=r["id"],
                category=r["category"],
                key=r["key"],
                value=r["value"],
                confidence=r["confidence"],
                importance=r["importance"],
                source=r["source"],
                is_archived=bool(r["is_archived"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in cursor.fetchall()
        ]

    def delete_memory(self, memory_id: str, hard_delete: bool = False) -> bool:
        """Soft delete (archive) or hard delete a memory record."""
        with self.db.transaction() as conn:
            if hard_delete:
                conn.execute("DELETE FROM memories WHERE id = ?;", (memory_id,))
                try:
                    conn.execute("DELETE FROM memories_fts WHERE memory_id = ?;", (memory_id,))
                except Exception:
                    pass
            else:
                conn.execute(
                    "UPDATE memories SET is_archived = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                    (memory_id,),
                )
        return True

    # ── Conversation History ─────────────────────────────────────────────────

    def start_conversation(self, title: str = "New Conversation", conv_id: Optional[str] = None) -> str:
        c_id = conv_id or str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title) VALUES (?, ?);",
                (c_id, title.strip()),
            )
        return c_id

    def add_message(self, conversation_id: str, role: str, content: str) -> str:
        msg_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content)
                VALUES (?, ?, ?, ?);
                """,
                (msg_id, conversation_id, role.strip(), content.strip()),
            )
            try:
                conn.execute(
                    "INSERT INTO messages_fts (message_id, role, content) VALUES (?, ?, ?);",
                    (msg_id, role.strip(), content.strip()),
                )
            except Exception:
                pass
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (conversation_id,),
            )
        return msg_id

    def get_messages(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        conn = self.db.get_connection()
        cursor = conn.execute(
            """
            SELECT id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC LIMIT ?;
            """,
            (conversation_id, limit),
        )
        return [dict(r) for r in cursor.fetchall()]

    def clear_conversation(self, conversation_id: str) -> bool:
        """Delete conversation and its associated messages."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?;", (conversation_id,))
        return True

    def update_conversation_summary(self, conversation_id: str, summary: str) -> bool:
        """Update the conversation summary."""
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE conversations SET summary = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (summary.strip(), conversation_id),
            )
        return True

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Fetch conversation details by ID."""
        conn = self.db.get_connection()
        cursor = conn.execute("SELECT * FROM conversations WHERE id = ?;", (conversation_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    # ── User Profile & Settings ──────────────────────────────────────────────

    def set_user_profile(self, key: str, value: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO user_profile (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP;
                """,
                (key.strip().lower(), value.strip()),
            )

    def get_user_profile(self, key: str) -> Optional[str]:
        conn = self.db.get_connection()
        cursor = conn.execute("SELECT value FROM user_profile WHERE key = ?;", (key.strip().lower(),))
        row = cursor.fetchone()
        return row[0] if row else None

    # ── Data Export ──────────────────────────────────────────────────────────

    def export_data(self) -> Dict[str, Any]:
        """Export all canonical memories, conversations, and user profile locally."""
        memories = [asdict(m) for m in self.list_memories(include_archived=True, limit=10000)]
        conn = self.db.get_connection()

        conversations = []
        c_cursor = conn.execute("SELECT * FROM conversations ORDER BY created_at DESC;")
        for c in c_cursor.fetchall():
            m_cursor = conn.execute(
                "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC;",
                (c["id"],),
            )
            conversations.append({
                "id": c["id"],
                "title": c["title"],
                "created_at": c["created_at"],
                "messages": [dict(m) for m in m_cursor.fetchall()],
            })

        p_cursor = conn.execute("SELECT key, value FROM user_profile;")
        profile = {row["key"]: row["value"] for row in p_cursor.fetchall()}

        return {
            "version": 1,
            "exported_at": str(uuid.uuid4()),
            "profile": profile,
            "memories": memories,
            "conversations": conversations,
        }

    # ── Non-Destructive Legacy Importer ──────────────────────────────────────

    def import_legacy_json_memories(self, memory_dir: Path | str) -> int:
        """
        Non-destructively imports records from existing memory/*.json files into SQLite.
        Preserves all original files completely.
        """
        mem_path = Path(memory_dir)
        if not mem_path.exists():
            return 0

        imported_count = 0
        for json_file in mem_path.glob("*.json"):
            if json_file.name in ("config.json", "memory_index.json", "failed_edits.json"):
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                records = []
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    records = data.get("memories", []) or data.get("records", []) or data.get("items", [])
                    if not records:
                        # Simple key-value dict (skip schema metadata)
                        category = json_file.stem
                        for k, v in data.items():
                            if k in ("schema_version", "category", "updated_at", "total_memories", "created_at"):
                                continue
                            if isinstance(v, (str, int, float, bool)):
                                self.save_memory(category, str(k), str(v), source="legacy_import")
                                imported_count += 1
                        continue

                category = data.get("category") or json_file.stem
                for r in records:
                    if isinstance(r, dict):
                        k = r.get("key") or r.get("title") or r.get("name") or "item"
                        v = r.get("value") or r.get("content") or r.get("text") or str(r)
                        conf = float(r.get("confidence", 0.8))
                        imp = int(r.get("importance", 5))
                        m_id = r.get("id")
                        src = r.get("source", "legacy_import")
                        self.save_memory(category, str(k), str(v), confidence=conf, importance=imp, source=src, memory_id=m_id)
                        imported_count += 1
            except Exception:
                pass

        return imported_count
