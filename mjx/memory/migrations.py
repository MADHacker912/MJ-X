"""
mjx.memory.migrations — Schema Migration Runner and Version Tracking.
"""

from __future__ import annotations

import sqlite3
from typing import Dict, List, Tuple
from .database import DatabaseManager
from .schema import INITIAL_SCHEMA_V1, FTS5_SCHEMA


class MigrationManager:
    """Applies versioned schema migrations transactionally."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_applied_versions(self) -> List[int]:
        """Return list of already applied schema migration version numbers."""
        conn = self.db.get_connection()
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations';"
            )
            if not cursor.fetchone():
                return []
            cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []

    def apply_all_migrations(self) -> int:
        """Apply all pending migrations. Returns count of applied migrations."""
        applied = set(self.get_applied_versions())
        pending: List[Tuple[int, str, str]] = [
            (1, "initial_schema_v1", INITIAL_SCHEMA_V1),
            (2, "fts5_search_v1", FTS5_SCHEMA),
        ]

        count = 0
        for version, name, ddl_script in pending:
            if version not in applied:
                self._apply_migration(version, name, ddl_script)
                count += 1
        return count

    def _apply_migration(self, version: int, name: str, ddl_script: str) -> None:
        with self.db.transaction() as conn:
            # Execute DDL statements
            conn.executescript(ddl_script)
            # Record in migrations table
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?);",
                (version, name),
            )
            print(f"[MemoryDB] ✅ Applied migration v{version}: {name}")
