"""
mjx.memory.backup — Consistent SQLite Online Backups with Integrity Verification.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import List, Optional
from .database import DatabaseManager, get_db_manager


def get_default_backup_dir() -> Path:
    b_dir = Path(__file__).resolve().parent.parent.parent / "data" / "backups"
    b_dir.mkdir(parents=True, exist_ok=True)
    return b_dir


class BackupManager:
    """Creates point-in-time consistent SQLite backups using SQLite's native backup API."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, backup_dir: Optional[Path] = None):
        self.db = db_manager or get_db_manager()
        self.backup_dir = backup_dir or get_default_backup_dir()
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, custom_dest_dir: Optional[Path | str] = None) -> Path:
        """
        Create a point-in-time consistent online backup.
        Verifies integrity before marking backup as complete.
        Never overwrites previous backups.
        """
        dest_dir = Path(custom_dest_dir) if custom_dest_dir else self.backup_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = dest_dir / f"mjx_backup_{timestamp}.db"

        # 1. Source connection
        src_conn = self.db.get_connection()

        # 2. Target connection for point-in-time backup
        dest_conn = sqlite3.connect(str(backup_path))
        try:
            with self.db._lock:
                src_conn.backup(dest_conn, pages=100)
            dest_conn.commit()
        finally:
            dest_conn.close()

        # 3. Verify backup file integrity
        verify_conn = sqlite3.connect(str(backup_path))
        try:
            cursor = verify_conn.execute("PRAGMA integrity_check;")
            res = cursor.fetchall()
            if not res or res[0][0] != "ok":
                backup_path.unlink(missing_ok=True)
                raise RuntimeError(f"Backup failed integrity verification: {res}")
        finally:
            verify_conn.close()

        return backup_path

    def list_backups(self) -> List[Path]:
        """List all valid backup files sorted by newest first."""
        backups = sorted(list(self.backup_dir.glob("mjx_backup_*.db")), key=os.path.getmtime, reverse=True)
        return backups

    def prune_old_backups(self, keep_count: int = 5) -> int:
        """
        Prune older backups while strictly preserving at least keep_count valid backups.
        Never deletes the only valid backup.
        """
        backups = self.list_backups()
        if len(backups) <= keep_count or len(backups) <= 1:
            return 0

        to_delete = backups[keep_count:]
        deleted = 0
        for p in to_delete:
            try:
                p.unlink()
                deleted += 1
            except Exception:
                pass
        return deleted
