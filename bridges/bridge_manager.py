"""
bridges/bridge_manager.py — Multi-Channel Bridge Orchestrator for MJ AI.
========================================================================
Manages connections to external messaging platforms (WhatsApp, Discord, Instagram),
routes incoming queries to MJ's Neural Brain and Gemini LLM, and dispatches responses.
"""

import sys
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _base_dir()
CHANNELS_CONFIG_PATH = BASE_DIR / "config" / "channels.json"


class BridgeManager:
    def __init__(self, on_log: Optional[Callable[[str], None]] = None, brain_callback: Optional[Callable[[str], str]] = None):
        self.on_log = on_log or (lambda msg: print(f"[BRIDGE-MGR] {msg}"))
        self.brain_callback = brain_callback
        self.whatsapp_bridge = None
        self._initialized = False

    def load_config(self) -> Dict[str, Any]:
        if CHANNELS_CONFIG_PATH.exists():
            try:
                return json.loads(CHANNELS_CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def start_enabled_bridges(self):
        """Starts all channels enabled in config/channels.json."""
        cfg = self.load_config()

        # 1. WhatsApp Bridge
        if cfg.get("whatsapp", {}).get("enabled", False):
            from bridges.whatsapp_bridge import get_whatsapp_bridge
            self.whatsapp_bridge = get_whatsapp_bridge(
                on_log=self.on_log,
                brain_callback=self.brain_callback
            )
            self.whatsapp_bridge.start()

        self._initialized = True

    def stop_all(self):
        """Stops all running channel bridges."""
        if self.whatsapp_bridge:
            self.whatsapp_bridge.stop()
            self.whatsapp_bridge = None

    def get_status(self) -> Dict[str, Any]:
        status = {
            "whatsapp": {"enabled": False, "connected": False},
            "discord":  {"enabled": False, "connected": False},
            "instagram":{"enabled": False, "connected": False},
        }
        cfg = self.load_config()
        if cfg.get("whatsapp", {}).get("enabled", False) and self.whatsapp_bridge:
            wa_stat = self.whatsapp_bridge.get_status()
            status["whatsapp"] = {
                "enabled": True,
                "connected": wa_stat.get("is_connected", False),
                "status": wa_stat.get("status", "offline")
            }
        return status


_global_manager: Optional[BridgeManager] = None

def get_bridge_manager(on_log=None, brain_callback=None) -> BridgeManager:
    global _global_manager
    if _global_manager is None:
        _global_manager = BridgeManager(on_log=on_log, brain_callback=brain_callback)
    return _global_manager
