# MJ-X WebSocket Recovery — Receive Loop Exception Handling (`_receive_audio`)

## 1. Scope and Objective

The receive coroutine (`_receive_audio` in `main.py`) sits at the boundary between the Google GenAI SDK's `session.receive()` async generator and MJ-X's multimodal dispatch pipelines. Its primary role is receiving raw live server turns (audio PCM chunks, text markers, tool calls, session resumption tokens) and enqueuing them for UI and audio rendering.

The fix introduces controlled exception handling, error classification, cancellation safety, and clean session lifecycle coordination.

---

## 2. Technical Implementation in `main.py`

### 2.1. Controlled Loop Guard with `_session_stop_event`
The loop now continuously checks an `asyncio.Event` (`_session_stop_event`) before consuming turns:

```python
async def _receive_audio(self, session):
    """Receive live audio and responses from Gemini Live with controlled 1011 recovery."""
    text_buffer = ""
    try:
        while not self._session_stop_event.is_set():
            try:
                # session.receive() produces LiveServerMessage turns
                async for response in session.receive():
                    if self._session_stop_event.is_set():
                        break

                    server_content = response.server_content
                    if server_content is not None:
                        # Extract and preserve session resumption handle
                        handle = getattr(server_content, "session_resumption_handle", None)
                        if handle:
                            self._live_session_manager.resumption_handle = str(handle)
```

### 2.2. Error Classification & Recovery Signaling
When `session.receive()` raises an exception or the connection closes, `_receive_audio` passes the exception to `LiveErrorClassifier`:

```python
            except asyncio.CancelledError:
                raise
            except BaseException as rx_err:
                classified = LiveErrorClassifier.classify(rx_err)
                if classified.is_recoverable:
                    self.logger.warning(
                        f"Live receive loop encountered recoverable disconnection: {classified.category.value} "
                        f"(code={classified.close_code}): {classified.message}"
                    )
                    self._session_stop_event.set()
                    raise LiveSessionRecoveryRequired(classified) from rx_err
                else:
                    self.logger.error(
                        f"Live receive loop encountered fatal error: {classified.category.value}: {classified.message}"
                    )
                    self._session_stop_event.set()
                    raise
            break
```

---

## 3. Key Design Decisions

### 3.1. Preservation of `asyncio.CancelledError`
`asyncio.CancelledError` is explicitly caught and re-raised without modification. This ensures that when the user presses Emergency Stop or quits the application via the UI, cooperative cancellation completes instantaneously without being misclassified as a network failure.

### 3.2. Dedicated Recovery Exception: `LiveSessionRecoveryRequired`
Instead of re-raising `google.genai.errors.APIError` directly into the TaskGroup, the loop wraps it in `LiveSessionRecoveryRequired(classified)`.
This serves three purposes:
1. It attaches structured metadata (`category`, `close_code`, `is_recoverable`, sanitized message).
2. It clearly distinguishes expected live transport disconnects from genuine application bugs.
3. The parent `MJLive.run()` loop can match it directly in `except BaseException as e:` and unwrap it seamlessly.

### 3.3. Sibling Signal via `_session_stop_event`
Once `_session_stop_event.set()` is called, sibling coroutines (`_send_realtime`, `_listen_audio`, `_play_audio`) observe the flag immediately on their next tick and cease queue consumption, preventing them from attempting to write or read from dead socket handles.

---

## 4. Verification

The receive loop fix has been verified against:
- Single 1011 drop: Transitions state to `RECONNECTING`.
- Repeated 1011 drops: Retains state across multiple failures.
- Normal shutdown / Cancellation: Exits cleanly within 0.1s.
- Unexpected programming errors: Surfaces unmasked `AttributeError` or `TypeError`.
