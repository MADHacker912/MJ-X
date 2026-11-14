# MJ-X PROJECT ECHO — MANUAL VERIFICATION & SMOKE TEST GUIDE

**Document:** Manual QA & Voice Testing SOP  
**Subsystem:** Live Microphone, Speaker & Emotion Dynamics  
**Date:** November 13, 2026  

---

## 1. Prerequisites for Manual Voice Testing

Ensure the following system audio devices are available:
- Linux audio framework: ALSA / PulseAudio / PipeWire.
- Functional microphone and speakers/headphones.
- Python packages installed: `sounddevice`, `numpy`, `PyQt6`.

---

## 2. Manual Verification Checklist

### Test 1: Live Voice Interruption (Barge-in)
1. Launch MJ-X: `python3 main.py`.
2. Ask a long question: *"Explain the architecture of SQLite WAL mode in detail."*
3. While the assistant is actively speaking, speak into the microphone at normal volume: *"Wait, pause."*
4. **Expected Result:**
   - Assistant immediately stops speaking within $\approx 200\text{ ms}$.
   - UI status switches from `SPEAKING` to `LISTENING`.
   - Assistant acknowledges the interruption without playing residual audio.

### Test 2: Audio Cleanliness at High Volume
1. In settings or console, set emotion to `excited` or `happy` with high intensity.
2. Listen to output speech through headphones.
3. **Expected Result:**
   - Sound is crisp and loud.
   - Zero audible clipping distortion, popping, or crackling during loud consonant bursts (e.g. *P*, *T*, *K*).

### Test 3: Emotion State Inertia & Natural Decay
1. Say: *"Bhai bohot funny tha ye joke 😂"*.
2. Observe UI avatar transitions to smiling/laughing with high intensity.
3. Wait quietly for 60–90 seconds without speaking.
4. **Expected Result:**
   - Avatar animation speed gradually slows down.
   - After the decay half-life, the emotion smoothly returns to `neutral` without abrupt visual jumps.

### Test 4: Emergency Stop Audio Cutoff
1. Trigger the global emergency stop hotkey or function while assistant is speaking.
2. **Expected Result:**
   - Audio output immediately cuts to complete silence.
   - Microphone stream stops forwarding packets.
   - No audio leaks until emergency stop is explicitly cleared.
