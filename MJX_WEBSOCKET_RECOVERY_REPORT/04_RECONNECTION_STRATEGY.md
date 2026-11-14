# MJ-X WebSocket Recovery — Reconnection Strategy & Backoff Algorithm

## 1. Overview

Reconnection after a transient server disconnection (such as HTTP 503 or WebSocket 1011) must satisfy two opposing requirements:
1. **Low Latency User Experience**: Reconnect as swiftly as possible so the user perceives minimal voice conversation downtime.
2. **Cluster Protection & Anti-Thundering Herd**: Avoid synchronized retry storms against Google GenAI backend clusters using exponential backoff and randomized jitter.
3. **Session Stability Awareness**: Prevent a cumulative retry limit from killing a session that has been running healthily for hours.

These requirements are implemented in `mjx/live/reconnect_policy.py` and `mjx/live/session_manager.py`.

---

## 2. Mathematical Backoff Model with Jitter

The backoff algorithm calculates the sleep duration $D_n$ for attempt $n$ using truncated exponential backoff modulated by uniform random jitter:

$$T_n = \min(D_{\max}, D_{\text{init}} \cdot F^{n-1})$$

$$\Delta = T_n \cdot J$$

$$D_n = \max(0.1, \text{random\_uniform}(T_n - \Delta, T_n + \Delta))$$

Where:
- $D_{\text{init}} = 1.5\text{ seconds}$ (Initial retry delay)
- $F = 2.0$ (Backoff multiplier)
- $D_{\max} = 60.0\text{ seconds}$ (Maximum backoff ceiling)
- $J = 0.25$ (±25% randomized uniform jitter)
- $N_{\max} = 10$ (Maximum consecutive retries before entering suspended state)

### 2.1. Delay Schedule Example (without jitter center-values)
- Attempt 1: $1.5\text{s} \pm 25\% \implies [1.125\text{s}, 1.875\text{s}]$
- Attempt 2: $3.0\text{s} \pm 25\% \implies [2.25\text{s}, 3.75\text{s}]$
- Attempt 3: $6.0\text{s} \pm 25\% \implies [4.50\text{s}, 7.50\text{s}]$
- Attempt 4: $12.0\text{s} \pm 25\% \implies [9.0\text{s}, 15.0\text{s}]$
- Attempt 5: $24.0\text{s} \pm 25\% \implies [18.0\text{s}, 30.0\text{s}]$
- Attempt 6+: Capped at $60.0\text{s} \pm 25\% \implies [45.0\text{s}, 75.0\text{s}]$

---

## 3. Session Stability Detection

A common defect in naive retry systems is monotonic incrementing of retry counters without a reset mechanism. Under that flawed design, if an assistant disconnects once every 3 hours, after 10 disconnects it would permanently fail, even though each connection ran smoothly for hours.

In `LiveSessionManager`:
```python
async def _monitor_stability(self) -> None:
    """Resets retry counter once the connection demonstrates sustained health."""
    try:
        await asyncio.sleep(self.policy.stable_threshold_secs)
        if self.state == ConnectionState.CONNECTED and self.retry_count > 0:
            self.log(
                f"🟢 Connection stable (>{self.policy.stable_threshold_secs}s healthy) — "
                f"resetting retry counter from {self.retry_count} to 0"
            )
            self.retry_count = 0
    except asyncio.CancelledError:
        pass
```

When a connection remains healthy for `stable_threshold_secs` (default: 20.0 seconds), the retry counter is reset to `0`. If a subsequent 1011 drop occurs, the system initiates recovery from the base delay (1.5s), minimizing user interruption.

---

## 4. State Transition Machine

```
              +-------------------+
              |   DISCONNECTED    |
              +---------+---------+
                        | connect()
                        v
              +-------------------+
              |    CONNECTING     |
              +---------+---------+
                        | session_established()
                        v
              +-------------------+
              |     CONNECTED     |<-------------------+
              +---------+---------+                    |
                        | 1011 / network drop          |
                        v                              |
              +-------------------+                    |
              |   RECONNECTING    |                    |
              | (Backoff + Jitter)|                    |
              +---------+---------+                    |
                |       |                              |
                |       +-- retry < max_retries -------+
                |
                +-- retry >= max_retries OR fatal (1007)
                v
              +-------------------+
              |  FAILED / SUSPEND |
              +-------------------+
```

---

## 5. Security & Privacy Guarantees in Logging

When network errors are logged, the diagnostics string passes through `LiveErrorClassifier._sanitize_message()`:
1. Google API keys (`AIza[0-9A-Za-z_-]{30,}`) are replaced with `[REDACTED_API_KEY]`.
2. URL token parameters (`key=...`) are replaced with `key=[REDACTED]`.
3. Error messages are capped at 200 characters to prevent log injection and terminal buffer poisoning.
