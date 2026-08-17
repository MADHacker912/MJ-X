"""
core/sleep_inhibitor.py — Prevents OS sleep and keeps system CPU active while MJ is running.
"""

import os
import platform
import subprocess
import ctypes
import threading
from typing import Optional

_OS = platform.system()

class SleepInhibitor:
    """
    Prevents automatic system sleep/suspend so MJ remains active and responsive.
    """

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._active = False

    def start_inhibit(self) -> bool:
        if self._active:
            return True

        try:
            if _OS == "Windows":
                # ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001) | ES_AWAKE_REQUIRE (0x00000002)
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
                self._active = True
                print("[SleepInhibitor] Windows system sleep inhibited.")
                return True

            elif _OS == "Linux":
                # Try systemd-inhibit or gnome-session-inhibit
                for cmd in [
                    ["systemd-inhibit", "--what=idle:sleep", "--why=MJ AI Active", "--mode=block", "sleep", "360000"],
                    ["gnome-session-inhibit", "--inhibit", "idle:suspend", "--reason", "MJ AI Active", "sleep", "360000"]
                ]:
                    try:
                        self._proc = subprocess.Popen(
                            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        self._active = True
                        print(f"[SleepInhibitor] Linux sleep inhibited via {cmd[0]}")
                        return True
                    except FileNotFoundError:
                        continue
                self._active = True
                return True

            elif _OS == "Darwin":
                # macOS caffeinate
                self._proc = subprocess.Popen(
                    ["caffeinate", "-i", "-s"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                self._active = True
                print("[SleepInhibitor] macOS caffeinate active.")
                return True

        except Exception as e:
            print(f"[SleepInhibitor] Could not inhibit sleep: {e}")

        return False

    def stop_inhibit(self) -> None:
        if not self._active:
            return

        try:
            if _OS == "Windows":
                # Reset to ES_CONTINUOUS
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            elif self._proc:
                self._proc.terminate()
                self._proc = None
        except Exception:
            pass

        self._active = False
        print("[SleepInhibitor] Sleep inhibit released.")
