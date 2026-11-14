# MJ-X PROJECT ECHO — ROLLBACK PROCEDURE

**Document:** Emergency Operational SOP  
**Subsystem:** Project ECHO P2 Voice & Emotion Runtime  
**Date:** November 13, 2026  

---

## 1. Safety Checkpoints Available

Prior to the commencement of P2 Project ECHO integration, a complete pre-integration safety tarball was created and stored in the repository:

- **Pre-P2 ECHO Tarball:** [`.checkpoints/checkpoint_p2_echo_pre.tar.gz`](file:///home/obito/Documents/MJ-X/.checkpoints/checkpoint_p2_echo_pre.tar.gz)
- **Pre-P1 Cortex Tarball:** [`.checkpoints/checkpoint_p1_cortex_pre.tar.gz`](file:///home/obito/Documents/MJ-X/.checkpoints/checkpoint_p1_cortex_pre.tar.gz)
- **Pre-Security Lockdown Tarball:** [`.checkpoints/checkpoint_security_lockdown_pre.tar.gz`](file:///home/obito/Documents/MJ-X/.checkpoints/checkpoint_security_lockdown_pre.tar.gz)

---

## 2. Fast Rollback Procedure (Single Command)

If immediate rollback to the pre-ECHO state is required:

```bash
cd /home/obito/Documents/MJ-X

# 1. Restore repository files from pre-P2 checkpoint
tar -xzf .checkpoints/checkpoint_p2_echo_pre.tar.gz

# 2. Verify git status
git status

# 3. Re-run tests to confirm baseline restoration
PYTHONPATH=. pytest tests/
```

---

## 3. Granular Rollback (Zero Downtime)

If you wish to retain test files and P1 Cortex unified memory while reverting emotion and voice runtime behavior:

1. **Disable emotion adaptation in settings:**
   In `memory/config.json` or through settings:
   ```json
   {
       "emotion_engine_enabled": false,
       "voice_emotions_enabled": false
   }
   ```
2. **Re-run application:**
   The application will immediately run in clean neutral voice mode without modifying source code.
