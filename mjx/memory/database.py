"""
mjx.memory.database — Thread-safe SQLite Connection Manager with WAL & Integrity Enforcement.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Generator, Optional


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def get_default_db_path() -> Path:
    data_dir = _base_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "mjx_local.db"


class DatabaseManager:
    """Manages thread-safe SQLite connections with strict durability pragmas."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else get_default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.RLock()
        self._initialized = False

    def get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=5.0,  # 5-second busy timeout
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row

            # Apply strict local-first safety PRAGMAs
            with conn:
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA synchronous = NORMAL;")
                conn.execute("PRAGMA busy_timeout = 5000;")
                conn.execute("PRAGMA temp_store = MEMORY;")

            self._local.conn = conn
        return conn

    @contextlib.contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for atomic database transactions with rollback on error."""
        conn = self.get_connection()
        with self._lock:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def check_integrity(self) -> tuple[bool, str]:
        """Run PRAGMA integrity_check to verify database health."""
        try:
            conn = self.get_connection()
            cursor = conn.execute("PRAGMA integrity_check;")
            rows = [row[0] for row in cursor.fetchall()]
            if rows == ["ok"]:
                return True, "ok"
            return False, "; ".join(rows)
        except Exception as exc:
            return False, str(exc)

    def close(self) -> None:
        """Close current thread-local connection."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None


# Global database manager
_default_db_manager = DatabaseManager()


def get_db_manager(db_path: Optional[Path | str] = None) -> DatabaseManager:
    if db_path is not None:
        return DatabaseManager(db_path)
    return _default_db_manager
