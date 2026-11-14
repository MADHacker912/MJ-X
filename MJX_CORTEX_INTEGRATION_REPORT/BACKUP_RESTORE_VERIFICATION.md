# MJ-X CORTEX RUNTIME UNIFICATION — BACKUP & RESTORE VERIFICATION REPORT

**Subsystem:** Cortex Backup & Disaster Recovery  
**Target Modules:** `mjx/memory/backup.py`, `mjx/memory/recovery.py`  
**Status:** FULLY VERIFIED & RESILIENT  
**Date:** November 13, 2026  

---

## 1. Online Backup Engine Architecture

MJ-X uses the native SQLite Online Backup API (`sqlite3_backup_*` wrapped via `src_conn.backup(dest_conn, pages=100)`).
- **Consistency:** Takes point-in-time consistent backups while write transactions are occurring in WAL mode.
- **Verification Gate:** Every generated backup file is checked with `PRAGMA integrity_check;` before being marked complete. If corruption is found, the file is unlinked immediately.
- **Preservation Policy:** Backups are written with ISO timestamps (`mjx_backup_YYYYMMDD_HHMMSS.db`). Existing backups are never overwritten.

---

## 2. Recovery Safety Contract

The restoration pipeline in `RecoveryManager.restore_backup()` implements a 3-layer safety contract:

```
[Trigger Restore(backup_path)]
            │
            ▼
[Layer 1: Test-Restore in Isolated Tempfile]
  ├── Verify file exists & non-empty
  ├── PRAGMA integrity_check == "ok"
  └── Verify required tables (memories, conversations, messages >= 3)
            │
            ├─► FAIL: Raise RuntimeError (Active DB untouched)
            │
            ▼ PASS
[Layer 2: Pre-Restore Safety Snapshot]
  └── Copy active db to data/mjx_pre_restore_safety_<timestamp>.db
            │
            ▼
[Layer 3: Atomic Restoration]
  ├── If active DB openable: Online Point-in-time restore via backup API
  └── If active DB corrupt: Close connections, unlink stale files, atomic copy
```

---

## 3. Test Verification Scenarios

### Scenario A: Online Hot Backup Creation
- Executed `memory_manager.backupMemory()`.
- Backup created in `data/backups/`.
- File validated: valid SQLite header, size > 0, passed `PRAGMA integrity_check;`.

### Scenario B: Severe Corruption Disaster Recovery
- Deliberately destroyed database header (first 100 bytes overwritten with garbage).
- `DatabaseManager.check_integrity()` correctly reported failure.
- `RecoveryManager.restore_backup(backup_path)` safely executed:
  1. Identified that active DB was unopenable.
  2. Preserved safety snapshot.
  3. Cleaned stale locks/WAL.
  4. Restored database atomically from verified backup.
- Subsequent `check_integrity()` returned `ok`. All records and FTS5 indices were intact.

### Scenario C: Post-Restore Data Fidelity
- Created conversation with user prompt: `"What is c?"`.
- Created backup.
- Cleared database completely (0 rows).
- Restored from backup.
- Verified: Both the conversation message and FTS search for `"light"` returned 100% exact matches.
