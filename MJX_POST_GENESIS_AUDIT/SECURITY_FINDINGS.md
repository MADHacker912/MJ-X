# MJ-X POST-GENESIS AUDIT — 04: SECURITY REVIEW & THREAT MODEL

**Audit Phase:** Phase 4 — OWASP, Threat Modeling & Critical Vulnerability Assessment  

---

## 1. THREAT AUDIT MATRIX

| Vulnerability Domain | Finding Description | Severity | CVSS v3.1 | Status |
|---|---|---|---|---|
| **Arbitrary Code Modification** | `core/self_modifier.py` exposed as tool `self_edit_file` in `main.py` without permission checks. | **CRITICAL** | **9.8** | ❌ UNMITIGATED |
| **Cleartext LAN Exposure** | `dashboard/server.py` binds to `0.0.0.0` with plain HTTP; tokens vulnerable to local sniffing. | **HIGH** | **7.5** | ❌ UNMITIGATED |
| **Unchecked File Operations** | `actions/file_processor.py` allows arbitrary file read/write across filesystem without permission ledger. | **HIGH** | **7.1** | ❌ UNMITIGATED |
| **Subprocess Leaks** | Legacy `actions/computer_control.py` & `flight_finder.py` invoke raw `subprocess` bypassing process isolation. | **MEDIUM** | **5.3** | ⚠️ PARTIAL |
| **Mobile PIN Brute-Force** | `mjx/aurora/pairing.py` 6-digit PIN has no rate-limiting or exponential backoff against local network flooding. | **MEDIUM** | **4.8** | ⚠️ PARTIAL |
| **Plaintext Credential Storage** | API keys in `api_keys.json` replaced by Keyring + Scrypt/AES-256-GCM. | **RESOLVED** | **—** | ✅ MITIGATED |
| **Child Env Secret Leakage** | API keys stripped from child environments in `SafeProcessManager`. | **RESOLVED** | **—** | ✅ MITIGATED |
| **Catastrophic Shell Commands**| `rm -rf`, `mkfs`, `format` blocked by process manager static inspection. | **RESOLVED** | **—** | ✅ MITIGATED |

---

## 2. DEEP DIVE ON CRITICAL VULNERABILITIES

### SEC-01: Arbitrary File Overwrite via `self_edit_file`
- **Location:** [`main.py`](file:///home/obito/Documents/MJ-X/main.py#L1474), [`core/self_modifier.py`](file:///home/obito/Documents/MJ-X/core/self_modifier.py)
- **Vulnerability Mechanism:**
  `main.py` registers `self_edit_file` as an active tool available to the Gemini Live model. When invoked, `self_modifier.self_edit_file` takes `target_relative_path` and `new_content` and writes it directly to disk.
- **Risk:**
  A prompt injection or confused-deputy attack over voice/web-search can induce the assistant to overwrite `main.py`, disable safety checks, or plant a persistent backdoor.
- **Remediation:** Remove `self_edit_file` from `TOOL_DECLARATIONS`, or restrict file writing to an isolated scratch sandbox requiring explicit physical GUI confirmation and `PermissionCategory.ADMIN_OPERATION`.

### SEC-02: Unencrypted HTTP Binding on `0.0.0.0`
- **Location:** [`dashboard/server.py`](file:///home/obito/Documents/MJ-X/dashboard/server.py#L813-L837)
- **Vulnerability Mechanism:**
  FastAPI server listens on `0.0.0.0:8000` (all interfaces) over unencrypted HTTP. Auth tokens (`sessionStorage.setItem('mj_token', tok)`) and remote commands (`/api/command`) travel in cleartext over the local network.
- **Risk:**
  Any device on the same local network (coffee shop WiFi, shared home network) can capture session tokens, eavesdrop on conversation broadcasts, or dispatch arbitrary commands.
- **Remediation:** Default host to `127.0.0.1` (loopback). Require explicit opt-in for LAN access and enforce TLS/HTTPS certificates or SSH tunnels.

### SEC-03: Arbitrary File System Access in `file_processor`
- **Location:** [`actions/file_processor.py`](file:///home/obito/Documents/MJ-X/actions/file_processor.py)
- **Vulnerability Mechanism:**
  File processor actions read and write paths directly without checking `mjx.security.permissions.PermissionCategory.FILE_WRITE` or `FILE_READ`.
- **Remediation:** Enforce `PermissionManager.check(PermissionCategory.FILE_WRITE)` prior to any disk modification.
