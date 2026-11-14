"""
mjx.live.connection_state — Connection Lifecycle and Error Categorization.
"""

from __future__ import annotations
from enum import Enum


class ConnectionState(str, Enum):
    """Lifecycle states of the Gemini Live WebSocket session."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    SUSPENDED = "suspended"
    FAILED = "failed"
    TERMINATED = "terminated"


class ErrorCategory(str, Enum):
    """Classification of errors occurring on the Gemini Live stream."""
    TRANSIENT_SERVER_ERROR = "transient_server_error"  # 1011, 1012, 1013, 500, 503, 504
    NETWORK_ERROR = "network_error"                    # 1006, timeout, DNS, reset
    NORMAL_CLOSURE = "normal_closure"                  # 1000, 1001
    AUTHENTICATION_ERROR = "authentication_error"      # 1007, invalid API key, 401, 403
    CONFIGURATION_ERROR = "configuration_error"        # invalid model, bad parameter, 400
    PROGRAMMING_ERROR = "programming_error"            # unhandled bug in application logic
