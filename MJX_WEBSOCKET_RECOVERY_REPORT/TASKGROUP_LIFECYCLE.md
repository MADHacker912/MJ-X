# MJ-X WebSocket Recovery — TaskGroup Lifecycle & Task Isolation

## 1. Problem Statement

Python 3.11's `asyncio.TaskGroup` provides structured concurrency with a strict guarantee: if any child task in the group raises an unhandled exception, **all other child tasks in the group are immediately cancelled**, and an `ExceptionGroup` is raised when exiting the context block.

In the original implementation of `main.py`, the TaskGroup contained:
1. `_send_realtime(session)` (Session-scoped)
2. `_listen_audio()` (Session-scoped)
3. `_receive_audio(session)` (Session-scoped)
4. `_play_audio()` (Session-scoped)
5. `_relay_phone_audio()` (Session-scoped)
6. `_run_system_monitor()` (Application-scoped)
7. `_run_background_monitor()` (Application-scoped)
8. `_run_proactive_mode()` (Application-scoped)
9. `_run_memory_maintenance()` (Application-scoped)
10. `_run_emotion_decay()` (Application-scoped)
11. `_dashboard.serve()` (Application-scoped)
12. `_process_dashboard_commands()` (Application-scoped)

When `1011 Internal error` occurred in task 3 (`_receive_audio`), tasks 6 through 12 were prematurely killed and had their internal state disrupted.

---

## 2. Decoupled Two-Tier Concurrency Architecture

The solution separates application-level persistent services from transient live-session tasks.

```
+-----------------------------------------------------------------------------------+
|                           MJ-X APPLICATION LIFECYCLE                              |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Persistent App Tasks (self._app_tasks - Spawned once, persist across 1011) |  |
|  | - System Monitor                                                            |  |
|  | - Background Proactive Monitor (maintains 5-min intervals)                  |  |
|  | - Memory Engine Maintenance / WAL Checkpoint                                |  |
|  | - Emotion Inertia & Decay Timer                                             |  |
|  | - FastAPI Localhost Dashboard Server & Queue Processor                      |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Transient Live Session Loop (While Running & Not Cancelled)                 |  |
|  |                                                                             |  |
|  |   async with asyncio.TaskGroup() as session_tg:                              |  |
|  |     - session_tg.create_task(_send_realtime(session))                       |  |
|  |     - session_tg.create_task(_listen_audio())                               |  |
|  |     - session_tg.create_task(_receive_audio(session))                       |  |
|  |     - session_tg.create_task(_play_audio())                                 |  |
|  |     - session_tg.create_task(_relay_phone_audio())                          |  |
|  |                                                                             |  |
|  |   On 1011 Disconnect:                                                       |  |
|  |     1. Sibling session tasks cancel cleanly                                 |  |
|  |     2. Hardware microphone & speaker release gracefully                     |  |
|  |     3. Audio in/out queues are drained                                      |  |
|  |     4. Backoff delay executes                                               |  |
|  |     5. New session TaskGroup created with fresh credentials                 |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 3. Implementation Details in `main.py`

### 3.1. One-Time Persistent Service Initialization
In `MJLive.run()`:
```python
# Start persistent application background tasks once
if not self._app_tasks:
    self._app_tasks = [
        asyncio.create_task(self._run_system_monitor(), name="app:system_monitor"),
        asyncio.create_task(self._run_background_monitor(), name="app:bg_monitor"),
        asyncio.create_task(self._run_proactive_mode(), name="app:proactive"),
        asyncio.create_task(self._run_memory_maintenance(), name="app:memory_maint"),
        asyncio.create_task(self._run_emotion_decay(), name="app:emotion_decay"),
    ]
    if self._dashboard_enabled:
        self._app_tasks.append(
            asyncio.create_task(self._dashboard.serve(), name="app:dashboard_server")
        )
        self._app_tasks.append(
            asyncio.create_task(self._process_dashboard_commands(), name="app:dashboard_cmds")
        )
```

### 3.2. Session-Scoped TaskGroup
The `session_tg` only manages tasks directly tied to the active Gemini Live socket:
```python
self._session_stop_event.clear()
async with asyncio.TaskGroup() as session_tg:
    session_tg.create_task(self._send_realtime(session))
    session_tg.create_task(self._listen_audio())
    session_tg.create_task(self._receive_audio(session))
    session_tg.create_task(self._play_audio())
    session_tg.create_task(self._relay_phone_audio())
```

### 3.3. Clean Teardown on Application Exit
In the `finally:` block of `MJLive.run()`, persistent application tasks are cancelled only when the user deliberately shuts down the application or when a non-recoverable fatal error occurs:
```python
finally:
    for task in self._app_tasks:
        if not task.done():
            task.cancel()
    if self._app_tasks:
        await asyncio.gather(*self._app_tasks, return_exceptions=True)
    self._app_tasks.clear()
    self._live_session_manager.dispose_current_session()
```

---

## 4. Benefits & Guarantees

1. **Zero State Disruption**: Proactive conversation timers, emotion decay curves, and SQLite memory checkpoints run uninterrupted during network reconnects.
2. **Deterministic Task Reclamation**: All session tasks are guaranteed terminated and joined before the next connection attempt begins, preventing duplicate workers.
3. **No Thread / Goroutine Leaks**: Verification tests prove that the task count returns to baseline after 1011 reconnection events.
