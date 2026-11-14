"""
mjx.aurora.sync_protocol — Mobile State Synchronization Protocol.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class DeviceState:
    device_id: str
    battery_level: int
    is_charging: bool
    wifi_connected: bool
    clipboard_content: Optional[str] = None
    last_seen: float = 0.0


class AuroraSyncProtocol:
    """Encodes, decodes, and validates state packets between MJ-X and Android companion."""

    def __init__(self):
        self._states: Dict[str, DeviceState] = {}

    def parse_mobile_telemetry(self, raw_json: str) -> Optional[DeviceState]:
        try:
            data = json.loads(raw_json)
            dev_id = str(data.get("device_id", "unknown"))
            state = DeviceState(
                device_id=dev_id,
                battery_level=max(0, min(100, int(data.get("battery", 100)))),
                is_charging=bool(data.get("charging", False)),
                wifi_connected=bool(data.get("wifi", True)),
                clipboard_content=data.get("clipboard"),
                last_seen=time.time(),
            )
            self._states[dev_id] = state
            return state
        except Exception:
            return None

    def get_device_state(self, device_id: str) -> Optional[DeviceState]:
        return self._states.get(device_id)

    def build_push_notification(self, title: str, body: str, action_url: Optional[str] = None) -> str:
        payload = {
            "type": "notification",
            "title": title,
            "body": body,
            "action_url": action_url,
            "timestamp": time.time(),
        }
        return json.dumps(payload)
