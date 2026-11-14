# MJ-X PROJECT ECHO — SECURITY & PRIVACY AUDIT

**Subsystem:** Permission Enforcement & Audio Privacy  
**Target Files:** `main.py`, `mjx/security/permissions.py`  
**Status:** COMPLIANT WITH ZERO DRIFT  
**Date:** November 13, 2026  

---

## 1. Hardware Permissions & Sandbox Invariants

1. **Explicit Permission Gates:** Microphone and Camera access require explicit user authorization registered in `PermissionManager` (`PermissionCategory.MICROPHONE` and `PermissionCategory.CAMERA`).
2. **No Continuous Background Audio Recording:** Audio capture streams are active **only** while the session is connected and unmuted. When the user toggles mute or disconnects, the microphone stream is immediately closed.
3. **Zero Silent Storage of Raw Audio:** Raw PCM audio bytes from user speech are streamed in memory directly to the secure WebSocket. Raw audio is **never written to disk, cached in temp directories, or mirrored in logs**.
4. **Log Sanitization:** Console logs, application audit trails, and dashboard WebSocket broadcasts output only text transcripts and emotion tokens (`emotion: happy, intensity: 0.8`), never raw audio binary.

---

## 2. Emergency Stop Preservation

The emergency stop circuit breaker (`is_emergency_stopped()`) is wired directly into all audio loops in `main.py`:

```python
# In microphone stream callback:
if self.ui.muted or self._phone_active or is_emergency_stopped():
    pre_roll.clear()
    hot_frames = 0
    return

# In speaker audio playback loop:
if is_emergency_stopped():
    self.set_speaking(False)
    break
```

When an emergency stop is triggered:
- Microphone input callback returns immediately without queueing audio.
- Speaker playback thread terminates immediately.
- Zero audio plays or records until `reset_emergency_stop()` is explicitly executed.

---

## 3. Psychological Safety & Emotional Privacy

1. **No Psychological Profiling:** The system does not classify or store medical, psychological, or psychiatric traits of the user.
2. **Ephemeral Mood Data:** Emotional state data resides strictly in volatile memory with exponential half-life decay. It is **never written to persistent SQLite tables** (`memories` or `user_profile`).
3. **Anti-Manipulation Constraint:** Every prompt injection includes mandatory instructions prohibiting the model from exploiting emotional vulnerability, fabricating personal attachment, or claiming human sentience.
