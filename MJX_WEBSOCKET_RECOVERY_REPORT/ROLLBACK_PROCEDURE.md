# MJ-X WebSocket Recovery — Rollback Procedure

## 1. Rollback Overview

In the unlikely event that unexpected regressions occur during field testing of the 1011 recovery subsystem, complete rollback can be executed instantaneously using the pre-fix tarball checkpoint or via selective git reversion.

---

## 2. Checkpoints Available

The following pre-fix and post-fix tarball archives are preserved under `.checkpoints/`:

| Checkpoint Name | File Path | Timestamp | Size | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Pre-Fix Checkpoint** | `.checkpoints/checkpoint_websocket_recovery_pre.tar.gz` | 2026-11-14 09:10 | 7.2 MB | Clean working state with 173 passing tests prior to 1011 fix |
| **Post-Fix Checkpoint** | `.checkpoints/checkpoint_websocket_recovery_post.tar.gz` | 2026-11-14 09:26 | 33 MB | Fully remediated state with 187 passing tests |

---

## 3. Rollback Instructions (Full Tarball Restoration)

To completely revert all changes to the exact pre-fix state:

```bash
cd /home/obito/Documents/MJ-X-test

# 1. Stop any running instances of MJ-X
pkill -f "python3.*main.py" || true

# 2. Extract the pre-fix checkpoint archive
tar -xzf .checkpoints/checkpoint_websocket_recovery_pre.tar.gz

# 3. Clean untracked recovery files if needed
rm -rf mjx/live
rm -f tests/test_websocket_recovery.py

# 4. Verify pre-fix baseline tests
PYTHONPATH=. pytest tests/ -q
# Expected output: 173 passed
```

---

## 4. Selective Component Rollback

If only specific components need adjustments while keeping the rest:

### A. Reverting Only `main.py`
If you wish to retain the `mjx.live` module for unit testing but revert the TaskGroup decoupling in `main.py`:
```bash
git checkout -- main.py
```

### B. Preserving Security and Cortex Modules
The files modified during this mission are strictly limited to:
- `main.py`
- `mjx/live/` (new package)
- `tests/test_websocket_recovery.py` (new test suite)

Unrelated systems (`mjx.security`, `mjx.memory`, `mjx.emotions`, `mjx.intelligence`, `dashboard/`) were untouched and require no restoration.
