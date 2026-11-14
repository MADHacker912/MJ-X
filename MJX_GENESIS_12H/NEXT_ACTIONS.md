# MJ-X GENESIS — NEXT ACTIONS & OPERATIONAL RUNBOOK

**Mission Status:** ALL AUTONOMOUS STAGES SUCCESSFULLY COMPLETED  
**Date:** 2026-11-13  

---

## 1. RECOMMENDED IMMEDIATE ACTIONS

1. **Production Packaging Run:**
   - Execute the Linux `.deb` packaging script in `scripts/package_deb.sh` or build Windows installer if deploying on Windows hosts.
2. **Android Companion APK Build:**
   - Run `cd android && ./build_apk.sh` to generate the latest debug APK with Aurora pairing support.
3. **Run User Verification Smoke Test:**
   - Launch `python main.py` in desktop environment to verify PyQt6 UI boots cleanly and connects to local vault.
4. **Backup Snapshot:**
   - Execute SQLite backup test:
     ```python
     from mjx.memory import DatabaseManager, LocalBackupManager
     db = DatabaseManager()
     bm = LocalBackupManager(db)
     bm.create_backup()
     ```
   - Verify backup file created in `data/backups/`.

---

## 2. DEVELOPER SOPs

- **Adding a new MCP Tool:**
  Use `mjx.skills.MCPAdapter.register_mcp_tool` with JSON Schema definition.
- **Granting Privileges in Actions:**
  Use `mjx.security.permissions.PermissionManager.check(category, action)` before touching hardware or executing commands.
- **Logging Sensitive Data:**
  Never log unmasked tokens. `mjx.security.process_manager.sanitize_env` and `mjx.security.vault.mask_secret` are available globally.
