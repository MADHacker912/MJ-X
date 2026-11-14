"""
mjx.live.reconnect_policy — Exponential Backoff with Jitter and Stability Detection.
"""

from __future__ import annotations
import random
import time
from dataclasses import dataclass


@dataclass
class ReconnectPolicy:
    """Calculates backoff delays and monitors connection stability."""
    initial_delay: float = 1.5
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter_ratio: float = 0.25  # +/- 25% random jitter
    stable_threshold_secs: float = 20.0  # Reset retry counter after 20s of healthy uptime

    def calculate_delay(self, attempt: int) -> float:
        """Compute exponential backoff with full/proportional jitter."""
        if attempt <= 0:
            base = self.initial_delay
        else:
            base = min(self.max_delay, self.initial_delay * (self.backoff_factor ** attempt))
        
        jitter_delta = base * self.jitter_ratio
        min_val = max(0.5, base - jitter_delta)
        max_val = min(self.max_delay, base + jitter_delta)
        delay = round(random.uniform(min_val, max_val), 2)
        return max(0.5, min(self.max_delay, delay))

    def is_connection_stable(self, connected_at: float, current_time: float | None = None) -> bool:
        """Check if the session has been active long enough to be considered stable."""
        if connected_at <= 0.0:
            return False
        now = current_time if current_time is not None else time.monotonic()
        return (now - connected_at) >= self.stable_threshold_secs
