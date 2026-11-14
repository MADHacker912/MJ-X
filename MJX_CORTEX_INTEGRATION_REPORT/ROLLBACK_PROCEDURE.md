# MJ-X CORTEX RUNTIME UNIFICATION — ROLLBACK PROCEDURE

**Document:** Emergency Operational SOP  
**Subsystem:** Cortex P1 Memory Runtime  
**Date:** November 13, 2026  

---

## 1. Safety Checkpoints Available

Prior to the commencement of P1 Cortex Runtime Unification, a complete pre-integration safety tarball was created and stored in the repository:

- **Pre-Integration Tarball:** [`.checkpoints/checkpoint_p1_cortex_pre.tar.gz`](file:///home/obito/Documents/MJ-X/.checkpoints/checkpoint_p1_cortex_pre.tar.gz)
- **Security Lockdown Tarball:** [`.checkpoints/checkpoint_security_lockdown_pre.tar.gz`](file:///home/obito/Documents/MJ-X/.checkpoints/checkpoint_security_lockdown_pre.tar.gz)

---

## 2. Fast Rollback Procedure (Single Command)

If immediate rollback to the pre-Cortex unification state is required:

```bash
cd /home/obito/Documents/MJ-X

# 1. Restore repository files from pre-P1 checkpoint
tar -xzf .checkpoints/checkpoint_p1_cortex_pre.tar.gz

# 2. Verify git status
git status

# 3. Re-run tests to confirm baseline restoration
PYTHONPATH=. pytest tests/
```

---

## 3. Granular Rollback (Zero Downtime)

If you wish to retain test files and security lockdown fixes while switching `memory_manager.py` back to standalone JSON storage:

1. **Disable SQLite routing in `memory/memory_manager.py`:**
   In [memory/memory_manager.py](file:///home/obito/Documents/MJ-X/memory/memory_manager.py), set:
   ```python
   def get_repository() -> MemoryRepository | None:
       return None  # Forces immediate 100% fallback to JsonMemoryStorage
   ```
2. **Re-run application:**
   The application will immediately read and write exclusively to `/memory/*.json` without deleting the SQLite database.

---

## 4. Database Disaster Recovery Runbook

If `data/mjx_local.db` becomes corrupted by an unexpected OS crash or hardware failure:

1. **Locate latest verified backup in `data/backups/`:**
   ```bash
   ls -lat data/backups/mjx_backup_*.db | head -n 1
   ```
2. **Run programmatic disaster recovery:**
   ```python
   from mjx.memory import DatabaseManager, RecoveryManager
   db_mgr = DatabaseManager()
   recovery = RecoveryManager(db_mgr)
   recovery.restore_backup("data/backups/mjx_backup_<TIMESTAMP>.db")
   ```
3. **Verify restored database health:**
   ```python
   ok, msg = db_mgr.check_integrity()
   print("Integrity Status:", ok, msg)
   ```
