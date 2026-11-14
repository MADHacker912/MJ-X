# MJ-X GENESIS FINAL REPORT — 12: SECURITY AND SAFETY

**Subsystem:** Cryptographic Credential Vault, Subprocess Isolation & Permission Ledger  
**Package:** `mjx.security`  

---

## 1. THREE-TIER CREDENTIAL VAULT

`mjx.security.vault.CredentialVault` eliminates plaintext secrets from disk:
1. **OS Secret Service Backend:** Uses native OS credential stores (`keyring.backends.SecretService` on Linux, Windows Credential Manager on Windows).
2. **Encrypted Fallback:** Uses authenticated AES-256-GCM encryption with high-work Scrypt KDF ($N=2^{14}, r=8, p=1$). Master recovery key is stored with strict `0600` POSIX file permissions.
3. **Memory & Exception Sanitization:** Regex filters strip credentials from stack traces, logs, and exception strings.

---

## 2. SUBPROCESS ISOLATION & SHIELD

`mjx.security.process_manager.SafeProcessManager`:
- Environment sanitization: Strips sensitive keys (`*_API_KEY`, `TOKEN`, `SECRET`, `PASSWORD`) from child environments.
- Memory capping: Caches output up to 2MB, actively terminating runaway output loops.
- Linux process groups (`preexec_fn=os.setsid`) and Windows window suppression (`CREATE_NO_WINDOW`).
- Static command inspection: Blocks destructive operations (`rm -rf`, `mkfs`, `format`, `dd`).

---

## 3. SCOPED PERMISSION LEDGER & DEAD-MAN SWITCH

`mjx.security.permissions.PermissionManager`:
- 11 distinct operational tiers.
- Non-sensitive operations auto-allowed; sensitive operations (`SCREEN_CAPTURE`, `CAMERA_ACCESS`, `FILE_WRITE`, `OS_INPUT_CONTROL`) require active time-bounded leases or one-time tokens.
- Instant emergency stop kill switch (`emergency_stop()`) immediately blocks all execution across the assistant.
- Append-only JSONL audit log records every permission decision.
