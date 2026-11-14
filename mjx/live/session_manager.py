"""
mjx.live.session_manager — Central Live Session Orchestrator & Recovery Controller.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, List, Optional

from mjx.live.connection_state import ConnectionState, ErrorCategory
from mjx.live.error_classifier import ClassifiedError, LiveErrorClassifier
from mjx.live.reconnect_policy import ReconnectPolicy


class LiveSessionManager:
    """
    Orchestrates Gemini Live connection lifecycle, error isolation,
    exponential backoff with jitter, stable connection detection,
    and clean audio pipeline recovery.
    """

    def __init__(
        self,
        policy: Optional[ReconnectPolicy] = None,
        on_state_change: Optional[Callable[[ConnectionState, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        self.policy = policy or ReconnectPolicy()
        self._on_state_change = on_state_change
        self._on_log = on_log

        self.state: ConnectionState = ConnectionState.DISCONNECTED
        self.retry_count: int = 0
        self.total_reconnects: int = 0
        self.connected_at: float = 0.0
        self.last_disconnect_at: float = 0.0
        self.last_error: Optional[ClassifiedError] = None
        self.resumption_handle: Optional[str] = None
        self._is_reconnecting: bool = False
        self._shutdown_requested: bool = False
        self._current_session: Any = None
        self._stability_task: Optional[asyncio.Task] = None

    def log(self, message: str) -> None:
        """Output privacy-safe, structured diagnostic log."""
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[LiveSession {timestamp}] {message}"
        print(formatted)
        if self._on_log:
            try:
                self._on_log(formatted)
            except Exception:
                pass

    def _set_state(self, new_state: ConnectionState, reason: str = "") -> None:
        prev = self.state
        self.state = new_state
        if prev != new_state:
            self.log(f"State transition: {prev.value} ➔ {new_state.value} ({reason})")
            if self._on_state_change:
                try:
                    self._on_state_change(new_state, reason)
                except Exception:
                    pass

    def on_connection_established(self, session: Any, resumption_handle: Optional[str] = None) -> None:
        """Called immediately after successful websocket handshake."""
        self._current_session = session
        self.connected_at = time.monotonic()
        self._is_reconnecting = False
        if resumption_handle:
            self.resumption_handle = resumption_handle

        self._set_state(ConnectionState.CONNECTED, "WebSocket connected successfully")
        self.log(
            f"🟢 Session established (attempt #{self.retry_count}, handle={self.resumption_handle or 'none'})"
        )

        # Cancel any previous stability checker
        if self._stability_task and not self._stability_task.done():
            self._stability_task.cancel()
        
        # Schedule background task to detect stable connection if an event loop is running
        try:
            loop = asyncio.get_running_loop()
            self._stability_task = loop.create_task(self._monitor_stability())
        except RuntimeError:
            self._stability_task = None

    async def _monitor_stability(self) -> None:
        """Resets retry counter once the connection demonstrates sustained health."""
        try:
            await asyncio.sleep(self.policy.stable_threshold_secs)
            if self.state == ConnectionState.CONNECTED and self.retry_count > 0:
                self.log(
                    f"🟢 Connection stable (>{self.policy.stable_threshold_secs}s healthy) — resetting retry counter from {self.retry_count} to 0"
                )
                self.retry_count = 0
        except asyncio.CancelledError:
            pass

    def on_connection_lost(self, exc: BaseException) -> Tuple[ClassifiedError, float]:
        """
        Processes disconnection, determines recoverability, and calculates backoff delay.
        Returns: (ClassifiedError, delay_seconds)
        """
        self.last_disconnect_at = time.monotonic()
        if self._stability_task and not self._stability_task.done():
            self._stability_task.cancel()

        classified = LiveErrorClassifier.classify(exc)
        self.last_error = classified
        code_str = f"code={classified.close_code}" if classified.close_code else "no close code"
        
        self.log(
            f"🔴 Session disconnected: {code_str} | classification={classified.category.value} | msg='{classified.message}'"
        )

        if not classified.is_recoverable:
            self._set_state(ConnectionState.FAILED, f"Fatal error: {classified.category.value}")
            return classified, 0.0

        self.retry_count += 1
        self.total_reconnects += 1
        delay = self.policy.calculate_delay(self.retry_count)
        self._set_state(
            ConnectionState.RECONNECTING,
            f"Recoverable {classified.category.value}; retry #{self.retry_count} in {delay:.2f}s",
        )
        self.log(
            f"🔄 Reconnection scheduled: attempt #{self.retry_count} with backoff delay {delay:.2f}s"
        )
        return classified, delay

    async def prepare_for_reconnect(self, delay: float) -> bool:
        """
        Sleeps for the computed backoff while checking for shutdown requests.
        Returns True if reconnect should proceed, False if aborted.
        """
        if self._shutdown_requested:
            return False

        self._is_reconnecting = True
        try:
            await asyncio.sleep(delay)
            return not self._shutdown_requested
        except asyncio.CancelledError:
            self.log("Reconnection sleep cancelled")
            return False

    async def dispose_current_session(self) -> None:
        """Cleanly releases existing session resources without raising."""
        session = self._current_session
        self._current_session = None
        if not session:
            return

        self.log("Disposing previous session resources...")
        try:
            # Check for close/close_async
            if hasattr(session, "close"):
                if asyncio.iscoroutinefunction(session.close):
                    await session.close()
                else:
                    session.close()
            elif hasattr(session, "_ws") and session._ws:
                if hasattr(session._ws, "close"):
                    await session._ws.close()
        except Exception as e:
            self.log(f"Notice: Session disposal completed with note ({e})")

    @staticmethod
    def drain_queue(q: asyncio.Queue) -> int:
        """Discards any stale audio buffers from a queue. Returns count discarded."""
        count = 0
        if not q:
            return 0
        while not q.empty():
            try:
                q.get_nowait()
                count += 1
            except (asyncio.QueueEmpty, ValueError):
                break
        return count

    def request_shutdown(self) -> None:
        """Signals clean shutdown — aborts reconnect loops."""
        self._shutdown_requested = True
        self._set_state(ConnectionState.TERMINATED, "Shutdown requested")
        if self._stability_task and not self._stability_task.done():
            self._stability_task.cancel()

    @property
    def is_shutting_down(self) -> bool:
        return self._shutdown_requested
