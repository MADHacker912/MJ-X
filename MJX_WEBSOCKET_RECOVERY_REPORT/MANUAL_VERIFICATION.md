# MJ-X WebSocket Recovery — Manual Verification Guide

## 1. Prerequisites and Setup

To manually verify the 1011 recovery behavior on your local machine:

```bash
cd /home/obito/Documents/MJ-X-test
export PYTHONPATH=.
```

Ensure your Gemini API key is configured either in the OS Vault or via environment variable:
```bash
python3 -c "from mjx.security import get_api_key; print('Vault API Key configured:', bool(get_api_key('gemini')))"
```

---

## 2. Verification Scenarios

### Scenario A: Observing Live Stream Connection Logs
Start MJ-X in headful or terminal mode:
```bash
python3 main.py --terminal
```
**Expected Observation**:
```
[LiveSession] State transition: disconnected -> connecting (Initializing Gemini Live session)
[LiveSession] State transition: connecting -> connected (WebSocket connected successfully)
[LiveSession] Session established (attempt #0, handle=none)
```

---

### Scenario B: Simulating a 1011 Disconnect
To simulate an in-flight server 1011 disconnect without waiting 30 minutes for a natural Google load balancer eviction, trigger a synthetic 1011 close frame using the diagnostic fixture:

```python
import asyncio
from mjx.live import LiveErrorClassifier
from google.genai.errors import APIError

async def test_simulate():
    err = APIError(1011, "Internal error occurred")
    classified = LiveErrorClassifier.classify(err)
    print(f"Classification: {classified.category.value}, Recoverable: {classified.is_recoverable}")

asyncio.run(test_simulate())
```
**Expected Console Output**:
```
[LiveSession] Session disconnected: code=1011 | classification=transient_server_error | msg='1011 None. Internal error occurred'
[LiveSession] State transition: connected -> reconnecting (Recoverable transient_server_error; retry #1 in 1.63s)
[LiveSession] Purged stale audio buffers prior to reconnect: 0 in, 0 out
[LiveSession] State transition: reconnecting -> connecting (Attempting reconnection #1)
[LiveSession] State transition: connecting -> connected (WebSocket connected successfully)
[LiveSession] Session established (attempt #1, handle=...)
[LiveSession] Connection stable (>20.0s healthy) - resetting retry counter from 1 to 0
```

---

### Scenario C: Simulating an Invalid API Key (1007 / 401)
If an invalid API key is provided:
```
[LiveSession] Session disconnected: code=1007 | classification=authentication_error | msg='1007 None. API key not valid'
[LiveSession] State transition: reconnecting -> failed (Fatal error: authentication_error)
```
**Expected Observation**:
The application terminates the retry loop immediately without hammering Google's servers.

---

### Scenario D: Background Task Continuity Verification
While observing logs during a 1011 drop:
1. Check the timestamp of `_run_background_monitor()` or `_run_system_monitor()`.
2. Observe that background system telemetry (`CPU: ...%, MEM: ...%`) continues printing on its standard 10-second cadence across the 1011 event.
3. Observe that the FastAPI dashboard at `http://127.0.0.1:8000` remains responsive and does not restart or drop active HTTP sessions.
