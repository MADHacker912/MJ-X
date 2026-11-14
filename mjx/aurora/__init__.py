"""
mjx.aurora — Android Companion Pairing and State Sync (Project AURORA).
"""

from mjx.aurora.pairing import AuroraPairingManager, PairingSession
from mjx.aurora.sync_protocol import AuroraSyncProtocol, DeviceState

__all__ = [
    "AuroraPairingManager",
    "PairingSession",
    "AuroraSyncProtocol",
    "DeviceState",
]
