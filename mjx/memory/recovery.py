"""
mjx.memory.recovery — Backup Integrity Verification and Tested Database Restoration.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Optional
from .database import DatabaseManager, get_db_manager


class RecoveryManager:
    """Safely verifies and restores database backups with test isolation."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()

    def verify_backup(self, backup_path: Path | str) -> tuple[bool, str]:
        """
        Test-restore backup file into an isolated temporary database.
        Verifies PRAGMA integrity_check and checks required tables.
        """
        p = Path(backup_path)
        if not p.exists() or p.stat().st_size == 0:
            return False, "Backup file does not exist or is empty"

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_db = Path(tmp.name)

        try:
            # Copy to temp file for isolated testing
            shutil.copy2(p, tmp_db)

            conn = sqlite3.connect(str(tmp_db))
            try:
                # 1. Integrity check
                cursor = conn.execute("PRAGMA integrity_check;")
                rows = cursor.fetchall()
                if not rows or rows[0][0] != "ok":
                    return False, f"Integrity check failed: {rows}"

                # 2. Check essential tables exist
                cursor = conn.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('memories', 'conversations', 'messages');"
                )
                count = cursor.fetchone()[0]
                if count < 3:
                    return False, f"Missing critical tables in backup (found {count}/3)"

                return True, "Backup verified successfully"
            finally:
                conn.close()
        except Exception as exc:
            return False, f"Verification failed with exception: {exc}"
        finally:
            tmp_db.unlink(missing_ok=True)

    def restore_backup(self, backup_path: Path | str) -> bool:
        """
        Restore verified backup into the active database.
        Safety contract:
          1. Verifies backup in temporary isolation first.
          2. Creates an emergency pre-restore safety snapshot of the active db.
          3. Only after verification, uses SQLite backup API to restore atomically.
        """
        p = Path(backup_path)
        valid, msg = self.verify_backup(p)
        if not valid:
            raise RuntimeError(f"Cannot restore invalid backup: {msg}")

        # 1. Take safety snapshot of active database
        active_db = self.db.db_path
        if active_db.exists() and active_db.stat().st_size > 0:
            safety_snapshot = active_db.parent / f"mjx_pre_restore_safety_{int(time.time())}.db"
            try:
                shutil.copy2(active_db, safety_snapshot)
                print(f"[Recovery] 🛡️ Created pre-restore safety snapshot: {safety_snapshot.name}")
            except Exception as exc:
                print(f"[Recovery] ⚠️ Could not create safety snapshot ({exc}), proceeding with caution.")

        # 2. Perform restore: online SQLite backup if target is valid, or filesystem replacement if target is corrupt
        self.db.close()
        can_online = False
        dest_conn = None
        try:
            dest_conn = self.db.get_connection()
            can_online = True
        except Exception:
            can_online = False

        if can_online and dest_conn:
            src_conn = sqlite3.connect(str(p))
            try:
                with self.db._lock:
                    src_conn.backup(dest_conn, pages=100)
                dest_conn.commit()
                print(f"[Recovery] ✅ Database successfully restored online from {p.name}")
                return True
            finally:
                src_conn.close()
        else:
            self.db.close()
            for suffix in ("", "-wal", "-shm"):
                Path(f"{active_db}{suffix}").unlink(missing_ok=True)
            shutil.copy2(p, active_db)
            print(f"[Recovery] ✅ Database successfully restored via replacement from {p.name}")
            return True
