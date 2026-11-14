"""
actions/phone_controller.py — Phone-level autonomous control action for MJ-X.
Dispatches touch, app launch, type, and system actions to the Android companion client.
"""

from collections import deque
import threading
from typing import Any, Dict, Optional

# Thread-safe queue for actions to be consumed by the Android client
_ACTION_QUEUE: deque = deque()
_QUEUE_LOCK = threading.Lock()
_LAST_SCREEN_DUMP: Dict[str, Any] = {}

# Common Android package names for fast mapping
APP_PACKAGES = {
    "whatsapp": "com.whatsapp",
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "spotify": "com.spotify.music",
    "settings": "com.android.settings",
    "camera": "com.android.camera",
    "dialer": "com.google.android.dialer",
    "contacts": "com.google.android.contacts",
    "maps": "com.google.android.apps.maps",
    "gmail": "com.google.android.gm",
    "telegram": "org.telegram.messenger",
    "instagram": "com.instagram.android",
    "calculator": "com.google.android.calculator",
}


def queue_phone_command(cmd: Dict[str, Any]) -> None:
    """Add a command to the queue for the connected Android phone."""
    with _QUEUE_LOCK:
        _ACTION_QUEUE.append(cmd)


def get_next_phone_command() -> Optional[Dict[str, Any]]:
    """Retrieve the next pending phone command (called by dashboard/server.py)."""
    with _QUEUE_LOCK:
        if _ACTION_QUEUE:
            return _ACTION_QUEUE.popleft()
    return None


def update_screen_dump(dump: Dict[str, Any]) -> None:
    """Store the latest screen hierarchy received from the phone."""
    global _LAST_SCREEN_DUMP
    _LAST_SCREEN_DUMP = dump


def phone_controller(
    parameters: Optional[Dict[str, Any]] = None,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
) -> str:
    """
    Executes actions directly on the connected Android phone.

    parameters:
      - action: 'open_app' | 'click' | 'type' | 'call' | 'swipe' | 'home' | 'back' | 'notifications'
      - app / package: name or package ID of the app (e.g. 'whatsapp', 'youtube')
      - text: text to type or text of the button to click
      - number: phone number for calls
      - x, y: coordinates for precision clicks
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if not action:
        return "Phone controller error: No action specified."

    if action in ("open_app", "launch_app"):
        app_name = params.get("app") or params.get("package") or ""
        app_key = app_name.lower().replace(" ", "")
        pkg = APP_PACKAGES.get(app_key, app_name)
        cmd = {"action": "launch_app", "package": pkg}
        queue_phone_command(cmd)
        return f"Queued phone action: Launching {app_name} ({pkg})"

    elif action in ("click", "click_text"):
        target_text = params.get("text") or params.get("target") or ""
        if not target_text and "x" in params and "y" in params:
            cmd = {"action": "click_coords", "x": float(params["x"]), "y": float(params["y"])}
            queue_phone_command(cmd)
            return f"Queued phone action: Click at ({params['x']}, {params['y']})"
        cmd = {"action": "click_text", "text": target_text}
        queue_phone_command(cmd)
        return f"Queued phone action: Click button '{target_text}'"

    elif action == "type":
        text_to_type = params.get("text", "")
        cmd = {"action": "type", "text": text_to_type}
        queue_phone_command(cmd)
        return f"Queued phone action: Typing '{text_to_type}'"

    elif action == "call":
        number = params.get("number") or params.get("phone") or ""
        cmd = {"action": "call_number", "number": number}
        queue_phone_command(cmd)
        return f"Queued phone action: Calling {number}"

    elif action in ("home", "back", "recents", "notifications"):
        cmd = {"action": action}
        queue_phone_command(cmd)
        return f"Queued phone action: Press {action}"

    elif action == "read_screen":
        cmd = {"action": "read_screen"}
        queue_phone_command(cmd)
        return "Requested screen hierarchy dump from phone."

    else:
        # Fallback generic dispatch
        queue_phone_command(params)
        return f"Queued custom phone action: {action}"
