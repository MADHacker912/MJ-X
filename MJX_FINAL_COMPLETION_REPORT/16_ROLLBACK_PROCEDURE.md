# MJ-X SINGULARITY — 16 ROLLBACK PROCEDURE

**Scope:** Emergency reversion protocols, checkpoint recovery, and fallback procedures.

---

## 1. AVAILABLE REPOSITORY CHECKPOINTS

Pre-allocated tarball backups located in `.checkpoints/`:

1. `checkpoint_p0_pre.tar.gz` — Pre-P0 security lockdown baseline.
2. `checkpoint_security_lockdown_pre.tar.gz` — Baseline immediately prior to P0 remediation.
3. `checkpoint_p1_cortex_pre.tar.gz` — Clean P0 baseline prior to P1 Cortex unification.
4. `checkpoint_p2_echo_pre.tar.gz` — Clean P1 baseline prior to P2 ECHO emotion unification.
5. `checkpoint_singularity_pre.tar.gz` — Clean P2 baseline prior to Singularity subsystem wiring.
6. `checkpoint_singularity_post.tar.gz` — Post-Singularity verified production baseline (173/173 tests passing).

---

## 2. EMERGENCY ROLLBACK TO PRE-SINGULARITY BASELINE

If unexpected integration conflicts emerge during production operations, revert immediately to `checkpoint_singularity_pre.tar.gz`:

```bash
cd /home/obito/Documents/MJ-X

# 1. Stop any running instances of MJ-X
pkill -f "python3 main.py"

# 2. Backup current database state
cp data/mjx_memory.db data/mjx_memory.db.bak.$(date +%s)

# 3. Extract the pre-singularity checkpoint
tar xzf .checkpoints/checkpoint_singularity_pre.tar.gz

# 4. Run test suite to verify baseline integrity
PYTHONPATH=. pytest tests/ -q
```

---

## 3. SQLITE DATABASE RECOVERY & REPAIR

If the local memory database (`data/mjx_memory.db`) becomes locked or corrupted:

```bash
cd /home/obito/Documents/MJ-X

# Check database integrity
sqlite3 data/mjx_memory.db "PRAGMA integrity_check;"

# Recover to fresh dump if corrupted
sqlite3 data/mjx_memory.db ".recover" | sqlite3 data/mjx_memory_recovered.db
mv data/mjx_memory_recovered.db data/mjx_memory.db

# Clear temporary write-ahead logs
rm -f data/mjx_memory.db-wal data/mjx_memory.db-shm
```

---

## 4. VAULT EMERGENCY RESET

To reset corrupted or locked encrypted credentials back to standard environment configuration:
```bash
cd /home/obito/Documents/MJ-X
rm -f config/.vault_manifest.json
# Ensure config/api_keys.json contains valid fallback credentials
```
