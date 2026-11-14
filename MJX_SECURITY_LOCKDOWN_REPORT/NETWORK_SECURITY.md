# MJ-X SECURITY LOCKDOWN — 04: NETWORK SECURITY & INTERFACE HARDENING

**Subsystem:** Dashboard Server, WebSocket Interfaces & Remote Companion Gating  
**File:** `dashboard/server.py`  

---

## 1. NETWORK TOPOLOGY & BINDING POLICIES

Prior to this remediation, `dashboard/server.py` listened on `0.0.0.0` (all IPv4 interfaces). This design permitted unauthenticated LAN probing of ports 8000 and 8001.

### Hardened Default Policy: Loopback Isolation
- The server now defaults strictly to `127.0.0.1`.
- Socket creation binds only to the local loopback interface:
  ```python
  env_host = os.environ.get("MJ_DASHBOARD_HOST")
  self.host = host or env_host or "127.0.0.1"
  ```
- Any connection attempt from an external IP on the local Wi-Fi/Ethernet network is refused at the kernel TCP layer with `Connection Refused`.

---

## 2. REMOTE ACCESS CONFIGURATION CONTRACT

If the operator requires remote access (e.g. for the Android companion app):
1. **Explicit Opt-In Required:**
   The operator must set the environment variable:
   ```bash
   export MJ_DASHBOARD_HOST=0.0.0.0
   ```
   or pass `DashboardServer(host="0.0.0.0")` programmatically.
2. **Security Warning Output:**
   When bound to a non-loopback interface, the server outputs:
   ```
   [Dashboard] ⚠️ WARNING: Server bound to 0.0.0.0. Remote LAN access is open.
   ```
3. **Firewall Hole Opening Policy:**
   - On `127.0.0.1`: `_ensure_network_access` is completely skipped.
   - On non-loopback interfaces: `_ensure_network_access` executes only when needed.

---

## 3. ENDPOINT AUTHENTICATION VERIFICATION

All sensitive API endpoints reject unauthenticated traffic with HTTP 401 Unauthorized:
- `POST /api/command`: Dispatches desktop commands; requires valid bearer token.
- `POST /api/wake`: Wakes the desktop interface; requires valid bearer token.
- `POST /api/upload`: Uploads files; requires valid bearer token.
- `GET /api/files`: Lists files; requires valid bearer token.
- `POST /login`: Validates one-time 6-character uppercase PIN; rate-limits invalid attempts.

Verified via automated test `test_dashboard_unauthorized_endpoints_rejected` in `tests/test_security_lockdown.py`.
