"""
actions/autopilot.py — Vision-guided autonomous desktop autopilot action.
"""

from typing import Any, Callable, Dict, Optional
import time
from actions.computer_control import computer_control
from actions.screen_processor import _capture_screen


def autopilot(
    parameters: Optional[Dict[str, Any]] = None,
    player: Any = None,
    speak: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Executes an autonomous vision-guided action or screen interaction.
    Supported actions in parameters:
      - action: 'task' | 'read' | 'click' | 'type'
      - task / description / query: string describe what to do or find
    """
    params = parameters or {}
    action_type = params.get("action", "task").lower().strip()
    task_desc = params.get("task") or params.get("description") or params.get("query") or ""

    if speak:
        speak(f"Starting autopilot {action_type} for: {task_desc or 'screen task'}")

    try:
        if action_type == "read":
            # Screen capture & read
            img_bytes = _capture_screen()
            if not img_bytes:
                return "Failed to capture screen."
            return "Screen captured successfully for analysis."

        elif action_type in ("click", "screen_click"):
            res = computer_control(parameters={"action": "screen_click", "description": task_desc})
            return res

        elif action_type == "type":
            text_to_type = params.get("text", "")
            if task_desc:
                computer_control(parameters={"action": "screen_click", "description": task_desc})
                time.sleep(0.3)
            res = computer_control(parameters={"action": "type", "text": text_to_type})
            return res

        else: # default "task" autonomous loop wrapper
            res = computer_control(parameters={"action": "screen_find", "description": task_desc})
            return f"Autopilot processed task '{task_desc}': {res}"

    except Exception as e:
        return f"Autopilot error: {e}"
