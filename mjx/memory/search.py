"""
mjx.memory.search — Full-Text Search with FTS5 and Fallback.
"""

from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional
from .database import DatabaseManager
from .normalization import normalize_hinglish_tokens, normalize_text


class MemorySearchEngine:
    """Provides FTS5 search with graceful fallback to LIKE queries."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._fts5_supported = self._check_fts5()

    def _check_fts5(self) -> bool:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts';"
            )
            return cursor.fetchone() is not None
        except Exception:
            return False

    def search_memories(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Search memories using FTS5 or fallback LIKE query.
        Returns ranked memory dictionaries.
        """
        tokens = normalize_hinglish_tokens(query)
        if not tokens:
            return []

        conn = self.db.get_connection()
        norm_cat = category.strip().lower() if category else None

        if self._fts5_supported:
            try:
                # Construct FTS5 match expression: token1 OR token2 OR ...
                match_expr = " OR ".join(f'"{t}"*' for t in tokens)
                sql = """
                    SELECT m.id, m.category, m.key, m.value, m.confidence, m.importance, m.source, m.created_at
                    FROM memories m
                    JOIN memories_fts f ON m.id = f.memory_id
                    WHERE memories_fts MATCH ?
                      AND m.is_archived = 0
                """
                params: list = [match_expr]
                if norm_cat:
                    sql += " AND m.category = ?"
                    params.append(norm_cat)
                sql += " ORDER BY rank LIMIT ?;"
                params.append(limit)

                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()
                if rows:
                    return [dict(row) for row in rows]
            except sqlite3.OperationalError:
                # Fallback to LIKE if match syntax fails
                pass

        # Fallback: Parameterized LIKE matching
        like_clauses = []
        params = []
        for t in tokens:
            like_clauses.append("(m.key LIKE ? OR m.value LIKE ?)")
            pattern = f"%{t}%"
            params.extend([pattern, pattern])

        where_like = " OR ".join(like_clauses)
        sql = f"""
            SELECT m.id, m.category, m.key, m.value, m.confidence, m.importance, m.source, m.created_at
            FROM memories m
            WHERE ({where_like}) AND m.is_archived = 0
        """
        if norm_cat:
            sql += " AND m.category = ?"
            params.append(norm_cat)
        sql += " ORDER BY m.importance DESC, m.updated_at DESC LIMIT ?;"
        params.append(limit)

        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def search_conversations(self, query: str, limit: int = 10) -> List[Dict]:
        """Search past message contents and conversation titles."""
        tokens = normalize_hinglish_tokens(query)
        if not tokens:
            return []

        conn = self.db.get_connection()

        if self._fts5_supported:
            try:
                match_expr = " OR ".join(f'"{t}"*' for t in tokens)
                sql = """
                    SELECT msg.id, msg.conversation_id, msg.role, msg.content, msg.created_at, c.title
                    FROM messages msg
                    JOIN messages_fts f ON msg.id = f.message_id
                    JOIN conversations c ON msg.conversation_id = c.id
                    WHERE messages_fts MATCH ?
                    ORDER BY rank LIMIT ?;
                """
                cursor = conn.execute(sql, (match_expr, limit))
                return [dict(row) for row in cursor.fetchall()]
            except Exception:
                pass

        # Fallback LIKE
        like_pattern = f"%{tokens[0]}%"
        sql = """
            SELECT msg.id, msg.conversation_id, msg.role, msg.content, msg.created_at, c.title
            FROM messages msg
            JOIN conversations c ON msg.conversation_id = c.id
            WHERE msg.content LIKE ? OR c.title LIKE ?
            ORDER BY msg.created_at DESC LIMIT ?;
        """
        cursor = conn.execute(sql, (like_pattern, like_pattern, limit))
        return [dict(row) for row in cursor.fetchall()]
