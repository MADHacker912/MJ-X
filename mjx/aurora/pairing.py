"""
mjx.aurora.pairing — Secure Android Companion Device Pairing.
"""

from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PairingSession:
    device_id: str
    pin_code: str
    token: str
    created_at: float
    expires_at: float
    is_authenticated: bool = False


class AuroraPairingManager:
    """Manages short-lived pairing PIN codes and authenticated device tokens."""

    def __init__(self, pin_ttl_secs: float = 300.0):
        self.pin_ttl_secs = pin_ttl_secs
        self._sessions: Dict[str, PairingSession] = {}
        self._authenticated_tokens: Dict[str, str] = {}  # token -> device_id

    def generate_pairing_code(self, device_id: str) -> PairingSession:
        pin = f"{secrets.randbelow(1000000):06d}"
        token = secrets.token_hex(24)
        now = time.time()
        session = PairingSession(
            device_id=device_id,
            pin_code=pin,
            token=token,
            created_at=now,
            expires_at=now + self.pin_ttl_secs,
            is_authenticated=False,
        )
        self._sessions[device_id] = session
        return session

    def verify_pin(self, device_id: str, pin_entered: str) -> Optional[str]:
        session = self._sessions.get(device_id)
        if not session:
            return None
        if time.time() > session.expires_at:
            self._sessions.pop(device_id, None)
            return None

        # Constant time compare
        if hmac.compare_digest(session.pin_code, pin_entered.strip()):
            session.is_authenticated = True
            self._authenticated_tokens[session.token] = device_id
            return session.token

        return None

    def is_token_valid(self, token: str) -> bool:
        return token in self._authenticated_tokens
