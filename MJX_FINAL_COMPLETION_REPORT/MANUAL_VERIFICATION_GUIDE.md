# MJ-X SINGULARITY — 14 MANUAL VERIFICATION GUIDE

**Purpose:** Step-by-step procedures for human verification of the unified MJ-X desktop assistant.

---

## 1. PRE-FLIGHT ENVIRONMENT CHECK

```bash
cd /home/obito/Documents/MJ-X

# 1. Verify Python version (3.11+)
python3 --version

# 2. Verify all tests pass
PYTHONPATH=. pytest tests/ -q

# 3. Verify clean import of main module
PYTHONPATH=. python3 -c "import main; print('MJ-X Core Ready')"
```

---

## 2. VERIFICATION PROCEDURE A: MEMORY & PERSISTENCE

1. Launch application:
   ```bash
   PYTHONPATH=. python3 main.py
   ```
2. Type in the input box:
   `"Mera project path /home/obito/Documents/MJ-X hai, yaad rakhna."`
3. Check application log:
   Confirm `[Memory] 💾 save_memory: notes/user_note` appears.
4. Exit application (Ctrl+Q or close window).
5. Inspect SQLite database directly:
   ```bash
   sqlite3 data/mjx_memory.db "SELECT category, key, value FROM memories WHERE key LIKE '%project%';"
   ```
   **Pass Criteria:** Value `/home/obito/Documents/MJ-X` is returned from SQLite.

---

## 3. VERIFICATION PROCEDURE B: OMNIBRAIN & TASK PLANNING

1. Launch application.
2. Type in input box:
   `"Pehle desktop organize karo fir system status check karo"`
3. Check application UI log:
   Confirm `Plan: ... (2 steps)` appears in the message log.
4. Verify response confirms multi-step intent execution.

---

## 4. VERIFICATION PROCEDURE C: GHOST AGENT SAFETY GATE

1. Open input box or voice command.
2. Instruct:
   `"Desktop control action task open browser"`
3. Confirm response in UI:
   `[GHOST AGENT] Safety guard veto: Permission denied for OS input control`
4. **Pass Criteria:** Action is rejected safely; mouse pointer does NOT move arbitrarily.

---

## 5. VERIFICATION PROCEDURE D: DASHBOARD & AURORA SYNC

1. Launch application.
2. In browser, navigate to: `http://127.0.0.1:8000/`
3. Click "Remote Control" in MJ-X desktop window to generate a pairing key.
4. Authenticate on the dashboard using the 6-character key.
5. In terminal, simulate companion sync telemetry:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/aurora/sync \
     -H "Content-Type: application/json" \
     -d '{"device_id": "test_phone", "battery": 92, "charging": true, "wifi": true}'
   ```
6. **Pass Criteria:** Returns `{"ok": true, "state": {...}}` with HTTP 200.

---

## 6. VERIFICATION PROCEDURE E: RUNTIME METRICS

1. Perform any 3 tool actions (e.g., `web_search`, `system_status`, `open_app`).
2. Ask MJ in the chat or terminal:
   Query tool `runtime_metrics`.
3. **Pass Criteria:** JSON payload returns with measured `success_rate` and `avg_duration_ms`.
