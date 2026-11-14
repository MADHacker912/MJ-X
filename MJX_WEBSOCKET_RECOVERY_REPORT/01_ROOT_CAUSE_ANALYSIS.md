# MJ-X WebSocket Recovery — Root Cause Analysis (1011 Internal Error)

## 1. Executive Summary

During sustained voice interactions with the Gemini Live API via `google-genai` (v2.23.0), the client application experienced unexpected disconnects accompanied by the following exception:

```
google.genai.errors.APIError: 1011 None. Internal error occurred
```

In the unpatched runtime (`/home/obito/Documents/MJ-X-test/main.py`), this exception propagated out of `_receive_audio()`, entered the enclosing `asyncio.TaskGroup()`, caused the immediate cancellation of all sibling coroutines, crashed the primary application runloop, and left microphone input/output streams and background services in an orphaned or broken state.

This document presents the technical analysis, protocol disassembly, SDK mechanics, and structural lifecycle defects that caused this cascading failure.

---

## 2. Gemini Live WebSocket Protocol & Code 1011 Disassembly

### 2.1. RFC 6455 WebSocket Close Code Semantics
Under RFC 6455 §7.4.1:
- **Status code 1011 (`Internal Error`)**:
  > *"1011 indicates that a server is terminating the connection because it encountered an unexpected condition that prevented it from fulfilling the request."*

Unlike code `1007` (Invalid payload / policy / authentication violation) or `1008` (Policy violation), `1011` represents a server-side condition, not a client protocol violation.

### 2.2. Upstream Gemini Live Architecture & 1011 Triggers
In the Google Gemini Live architecture (`generativelanguage.googleapis.com`), bidirectional audio and tool execution are streamed over an HTTP/2 or WebSocket connection. Code 1011 occurs under the following deterministic server conditions:
1. **Server Worker Eviction / Rolling Deployments**: Backend Gemini inference worker nodes are periodically recycled or rebalanced by Google's global load balancers.
2. **Session Lifespan Ceilings**: Active Live WebSocket sessions are governed by a server-side duration cap (typically between 15 and 30 minutes of continuous bidirectional streaming).
3. **Transient Server-Side GPU/TPU Capacity Pressure**: Temporary scheduling hiccups or timeout blips in audio decoding / tensor ingestion trigger a graceful closure from the server side.
4. **Session Resumption Checkpointing**: Google's API transmits session handles intended for client reconnection without losing multi-turn state.

### 2.3. Google GenAI SDK (v2.23.0) Exception Translation
In `google/genai/live.py:AsyncSession._receive`:
```python
try:
    raw_message = await self._ws.recv()
except websockets.exceptions.ConnectionClosedError as e:
    raise APIError(code=e.code, response_json=e.reason, response=None) from e
```
When Google closes the WebSocket with `1011`, the underlying `websockets` library receives close frame `1011` with reason `"Internal error occurred"`.
The SDK catches `ConnectionClosedError` and raises `google.genai.errors.APIError(1011, "Internal error occurred")`.

---

## 3. The Cascading Failure in MJ-X Runtime

Prior to the remediation, four critical structural defects existed in `main.py`:

### Defect 1: ExceptionGroup Cancellation Propagation in `asyncio.TaskGroup`
In `MJLive.run()`:
```python
# PRE-FIX CODE (main.py:2426)
async with asyncio.TaskGroup() as tg:
    tg.create_task(self._send_realtime(session))
    tg.create_task(self._listen_audio())
    tg.create_task(self._receive_audio(session))
    tg.create_task(self._play_audio())
    tg.create_task(self._run_system_monitor())        # <--- Application background task
    tg.create_task(self._run_background_monitor())    # <--- Application background task
    tg.create_task(self._run_proactive_mode())        # <--- Application background task
    tg.create_task(self._run_memory_maintenance())    # <--- Application background task
    tg.create_task(self._run_emotion_decay())         # <--- Application background task
```
**Mechanism of Failure**:
Python 3.11's `asyncio.TaskGroup` enforces strict all-or-nothing structured concurrency. When `_receive_audio` encountered `1011`, the TaskGroup cancelled **all** sibling tasks.
Critically, long-running application services (proactive assistant, system monitor, emotion decay, memory maintenance) were grouped inside the same TaskGroup as the ephemeral network tasks. When a temporary 1011 network blip occurred, the entire assistant died, resetting background timers and restarting 5-minute wait loops.

### Defect 2: Naive Exception Suppression and Missing Classification
In `_receive_audio()`:
```python
# PRE-FIX CODE
except Exception as e:
    logger.error(f"Error receiving audio: {e}")
    raise
```
The application treated a routine, recoverable 1011 server eviction identically to fatal bugs like `AttributeError` or invalid API key (`1007`), re-raising it raw without signaling the session recovery loop.

### Defect 3: Stale Audio Pipeline Poisoning
When the WebSocket connection was severed:
- `self.audio_in_queue` and `self.audio_out_queue` retained partially buffered PCM chunks from the old session.
- Audio input streams (`sd.InputStream`) were cancelled abruptly without invoking `.stop()` and `.close()`, causing ALSA/PulseAudio/PipeWire resource leaks and `PortAudioError: Device unavailable` on subsequent attempts.
- When the socket reconnected, the stale output audio from before the disconnect was dumped to the speaker, resulting in corrupted, lagging playback.

### Defect 4: Missing Backoff Jitter and Session Stability Tracking
The legacy reconnection loop utilized a simplistic fixed retry counter. If disconnects occurred repeatedly, requests slammed Google's servers synchronously without randomized jitter, triggering secondary rate limits (`429 Too Many Requests`). Furthermore, successful sustained connections never reset the retry counter, causing a healthy connection that ran for hours to fail permanently on its next brief blip.

---

## 4. Root Cause Classification Matrix

| Error Type | Trigger | Code | Recoverable? | Remediated Action |
| :--- | :--- | :--- | :--- | :--- |
| **Transient Server Eviction** | Server load shedding, worker reboot | `1011` | **YES** | Drain queues, backoff with jitter, transparent reconnect |
| **Transient Network Drop** | TCP socket closed, drop without frame | `1006` | **YES** | Backoff with jitter, re-establish socket |
| **Server Overload** | Rate limit / HTTP 503 / 504 | `503` / `504` | **YES** | Exponential backoff up to 60s |
| **Invalid Authentication** | Expired / bad GEMINI_API_KEY | `1007` / `401` | **NO** | Abort retries, alert user to update Vault secret |
| **Bad Session Config** | Unsupported model, invalid schema | `400` | **NO** | Abort retries, log configuration error |
| **Application Bug** | `AttributeError`, `ZeroDivisionError` | None | **NO** | Bubble up, fail fast without masking |

---

## 5. Conclusion

The `1011 Internal error occurred` is a normal, expected event in long-lived Gemini Live streams. The failure of MJ-X was not the error itself, but the lack of isolation between session-scoped network coroutines and application-scoped services, combined with unmanaged TaskGroup cancellation and unpurged audio buffers.

The fix isolates lifecycles, classifies errors dynamically, drains audio buffers, and applies exponential backoff with stability tracking.
