import platform as _platform
import subprocess as _subprocess

# ── Nuclear: force CREATE_NO_WINDOW on EVERY subprocess call on Windows ───────
# This patches Popen itself, so no per-file flag is needed anywhere.
if _platform.system() == "Windows":
    _OrigPopen = _subprocess.Popen

    class _Popen(_OrigPopen):
        def __init__(self, args, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | _subprocess.CREATE_NO_WINDOW
            kw.pop("startupinfo", None)   # drop any stale/shared STARTUPINFO
            super().__init__(args, **kw)

    _subprocess.Popen = _Popen
# ─────────────────────────────────────────────────────────────────────────────

# GNOME's Xwayland may store its MIT-MAGIC-COOKIE with an empty display
# number (meaning "any display").  The old python3-xlib used by PyAutoGUI
# rejects that valid wildcard and aborts while importing mouseinfo.  Teach it
# the wildcard semantics before any action module imports PyAutoGUI.
if _platform.system() == "Linux":
    try:
        from Xlib import error as _xlib_error
        from Xlib import xauth as _xlib_xauth

        _original_get_best_auth = _xlib_xauth.Xauthority.get_best_auth

        def _get_best_auth_with_display_wildcard(
            self, family, address, display_number,
            types=(b"MIT-MAGIC-COOKIE-1",),
        ):
            try:
                return _original_get_best_auth(
                    self, family, address, display_number, types
                )
            except _xlib_error.XNoAuthError:
                address_bytes = (
                    address.encode() if isinstance(address, str) else address
                )
                matches = {
                    auth_name: auth_data
                    for entry_family, entry_address, entry_number,
                        auth_name, auth_data in self.entries
                    if entry_family == family
                    and entry_address == address_bytes
                    and entry_number == b""
                }
                for auth_type in types:
                    if auth_type in matches:
                        return auth_type, matches[auth_type]
                raise

        _xlib_xauth.Xauthority.get_best_auth = (
            _get_best_auth_with_display_wildcard
        )
    except ImportError:
        pass
# ─────────────────────────────────────────────────────────────────────────────────────────

import asyncio
from collections import deque
import re
import threading
import time
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import sounddevice as sd
import numpy as np
from google import genai
from google.genai import types
from ui import MJUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    save_session_summary, pop_last_session, searchMemory,
    format_relevant_memory_for_prompt, learnFromConversation, cleanupMemory,
    summarizeConversation,
)
from emotion import EmotionEngine, SUPPORTED_EMOTIONS
from emotion.voice import apply_pcm16_settings
from personality import FriendPersonalityEngine

from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import _capture_camera, _capture_screen, get_last_camera_photo
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.ponytail          import ponytail_action
from actions.slopwatch         import slopwatch_action
from actions.whatsapp_action   import whatsapp_action
from actions.notes_action      import notes_action
from actions.system_optimizer  import system_optimizer
from bridges.bridge_manager    import get_bridge_manager
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.autopilot         import autopilot as autopilot_action
from actions.openclaw_integration import openclaw_task
from actions.system_monitor    import SystemMonitor, get_system_status
from actions.proactive         import ProactiveEngine
from core.sleep_inhibitor import SleepInhibitor
from core.autonomous_learner import AutonomousLearner
from core.self_modifier import self_edit_file, create_codebase_backup
from core.neural_brain import get_neural_brain
from actions.background_monitor import (
    add_monitor, remove_monitor, list_monitors, check_all as monitor_check_all,
)
from actions.web_search        import _news as _fetch_news_sync
from actions.screen_processor  import (
    _capture_camera, _capture_screen, get_last_camera_photo,
    show_last_camera_photo, take_photo,
)
from memory.config_manager     import (
    get_brief_enabled, get_emotion_settings, get_voice_interruption_enabled,
)


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024
INPUT_AUDIO_MIME    = f"audio/pcm;rate={SEND_SAMPLE_RATE}"


def _restart_command() -> list[str]:
    """Return the exact command needed to launch a fresh MJ process."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *sys.argv[1:]]
    return [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]


def _barge_in_threshold(ambient_rms: float, output_rms: float) -> float:
    """Adaptive microphone threshold that rejects ambient noise and speaker echo."""
    return max(650.0, ambient_rms * 3.2, output_rms * 0.22)

def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are MJ, Saksham's Female AI Assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


def _normalize_transcript(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _append_output_transcript(out_buf: list[str], text: str) -> None:
    """Append a new output transcription segment while suppressing repeats."""
    text = _clean_transcript(text)
    if not text:
        return
    norm_text = _normalize_transcript(text)
    if not norm_text:
        return
    if out_buf:
        last_text = out_buf[-1]
        last_norm = _normalize_transcript(last_text)
        if norm_text == last_norm:
            return
        if norm_text.startswith(last_norm):
            out_buf[-1] = text
            return
        if last_norm.startswith(norm_text):
            return
        # Avoid repeated segments from earlier in the same turn
        for prev in reversed(out_buf[-3:]):
            if _normalize_transcript(prev) == norm_text:
                return
    out_buf.append(text)

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer OR lists all currently open applications. "
            "Use action='list' or app_name='list' when the user asks what applications are open, "
            "how many apps are running, or to list open programs."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":   {"type": "STRING", "description": "open | list (default: open)"},
                "app_name": {"type": "STRING", "description": "Name of app to open (or 'list' to show open apps)"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": (
            "Searches the web. Use for ANY question about current facts, events, prices, "
            "or topics — always prefer this over guessing. "
            "Modes: 'search' (default), 'news' (latest headlines on a topic), "
            "'research' (deep comprehensive answer), 'price' (product cost lookup), "
            "'compare' (side-by-side comparison of items)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query or topic"},
                "mode":   {"type": "STRING", "description": "search | news | research | price | compare"},
                "items":  {"type": "ARRAY",  "items": {"type": "STRING"}, "description": "Items to compare (compare mode)"},
                "aspect": {"type": "STRING", "description": "Comparison aspect: price | specs | reviews | features"},
            },
            "required": ["query"]
        }
    },
    {
        "name": "system_status",
        "description": (
            "Returns real-time system metrics: CPU usage, RAM, GPU load, CPU temperature, "
            "uptime, and process count. Use when the user asks about computer performance, "
            "temperature, memory, or resource usage."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures the screen or webcam image and lets you analyze it. "
            "MUST be called when user asks what is on screen, what you see, "
            "look at camera, analyze my screen, etc. "
            "You have NO visual ability without this tool. "
            "After the image is captured it is sent directly to you — describe what you see and answer the user's question. "
            "When using camera: the live view stays open until user says close it or calls close_camera."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "close_camera",
        "description": (
            "Closes the live camera view shown on screen. "
            "Call when user says: close camera, stop camera, turn off camera, "
            "close camera, stop camera, band karo camera, creepy, etc."
        ),
        "parameters": {"type": "OBJECT", "properties": {}, "required": []}
    },
    {
        "name": "show_last_photo",
        "description": (
            "Displays the most recently captured camera photo in the UI overlay and returns its saved file path. "
            "Use when the user asks to show the last photo or image you captured."
        ),
        "parameters": {"type": "OBJECT", "properties": {}, "required": []}
    },
    {
        "name": "take_photo",
        "description": (
            "Clicks/takes a real photo using the camera and saves it into the Photos/MJ directory. "
            "Call ONLY when the user explicitly requests to click a photo, take a picture, 'photo click karo', 'photo kheencho', 'snap a photo', etc. "
            "Do NOT call this during general vision analysis ('camera me dekh ke batao') unless explicit photo clicking is asked."
        ),
        "parameters": {"type": "OBJECT", "properties": {}, "required": []}
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, computer restart, computer shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use restart/shutdown here only when the user explicitly means the PC or operating system. "
            "To restart MJ itself, use restart_mj."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls any web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, screenshots, navigation, any web-based task. "
            "Simple open/search requests launch the user's own browser normally (their real profile "
            "and logged-in accounts); interactive actions (click, type, fill_form...) attach an "
            "automation browser. "
            "Always pass the 'browser' parameter when the user specifies a browser (e.g. 'open in Edge', "
            "'use Firefox', 'open Chrome'). Multiple browsers can run simultaneously."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | list_tabs | screenshot | back | forward | reload | switch | list_browsers | close | close_all"},
                "browser":     {"type": "STRING", "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the currently active browser."},
                "url":         {"type": "STRING", "description": "URL for go_to / new_tab action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "engine":      {"type": "STRING", "description": "Search engine: google | bing | duckduckgo | yandex (default: google)"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up | down for scroll"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount in pixels (default: 500)"},
                "key":         {"type": "STRING", "description": "Key name for press action (e.g. Enter, Escape, F5)"},
                "path":        {"type": "STRING", "description": "Save path for screenshot"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "self_edit",
        "description": (
            "Safely edit a workspace file directly. Use only when the user explicitly requests MJ to modify its own code. "
            "Write the full file content in the 'content' field. The file must reside inside the MJ workspace."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Workspace-relative or absolute path to the file to edit."},
                "content":   {"type": "STRING", "description": "The exact file contents to write."},
                "summary":   {"type": "STRING", "description": "Optional short summary of the change."},
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "neural_status",
        "description": (
            "Returns diagnostics and self-learning telemetry for MJ's internal Neural Brain "
            "(learning steps, code risk assessment accuracy, and weight parameters)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "code_helper",
        "description": (
            "ALWAYS call this tool when the user asks to create, write, generate, edit, "
            "run, optimize or save ANY code file or code snippet (e.g. while loop script, python script, desktop file). "
            "Do NOT just reply with text claiming the file was created; you MUST call this tool to write and save the file to disk."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: write)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file (default: Desktop/while_loop.py)"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action", "description"]
        }
    },
    {
        "name": "ponytail",
        "description": (
            "Senior Developer minimalist coding engine. Use whenever asked to simplify code, audit for over-engineering, "
            "remove bloat, replace libraries with Python stdlib, or write the shortest, cleanest working solution (YAGNI)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "audit | review | simplify | set_mode | help (default: review)"},
                "target": {"type": "STRING", "description": "File path, directory, or raw code snippet to analyze/simplify"},
                "level":  {"type": "STRING", "description": "Intensity level: lite | full | ultra"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "slopwatch",
        "description": (
            "SlopWatch AI Anti-Cheat & Reward Hacking Detector. Use when asked to check for AI slop, "
            "disabled tests, suppressed warnings, swallowed exceptions, arbitrary sleep/delays, or CPM bypasses."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "scan | analyze | audit (default: scan)"},
                "target": {"type": "STRING", "description": "File or directory path to scan for AI slop"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "whatsapp",
        "description": (
            "Advanced WhatsApp Assistant: Check recent messages, get AI summary of unread chats, "
            "send messages by contact name (e.g. 'Rahul') or phone number, list contacts, or add contacts."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":  {"type": "STRING", "description": "recent | summary | send | list_contacts | add_contact | status (default: recent)"},
                "to":      {"type": "STRING", "description": "Contact name (e.g. 'Rahul', 'Mummy') or phone number with country code"},
                "text":    {"type": "STRING", "description": "Message text to send (for send action) or note"},
                "limit":   {"type": "INTEGER", "description": "Number of messages to retrieve (default: 10)"},
                "name":    {"type": "STRING", "description": "Contact name (for add_contact)"},
                "number":  {"type": "STRING", "description": "Phone number (for add_contact)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "notes_memo",
        "description": (
            "Smart Notes & Memos: Take notes, save ideas, create todo items, search through notes, or list all saved notes for Boss."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":   {"type": "STRING", "description": "add | list | search | delete | clear (default: list)"},
                "text":     {"type": "STRING", "description": "Note content to save or delete"},
                "category": {"type": "STRING", "description": "Optional category (e.g. Work, Ideas, Todo, Meeting)"},
                "query":    {"type": "STRING", "description": "Keyword to search for in notes"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "system_optimizer",
        "description": (
            "AI System Health & Resource Optimizer: Free up RAM buffers, clean temporary cache files, identify top CPU/RAM processes, and check battery/thermal health."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "optimize | free_ram | top_processes | clean_temp | battery (default: optimize)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "terminal_control",
        "description": (
            "Opens, closes, or executes commands in the embedded GUI Terminal panel on screen. "
            "Use when the user asks to open terminal, toggle terminal, or run a terminal command visibly in the UI."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":  {"type": "STRING", "description": "open | close | toggle | run | clear (default: toggle)"},
                "command": {"type": "STRING", "description": "Optional shell command to execute in the terminal"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use browser_control or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "manage_monitor",
        "description": (
            "Add, remove, or list background monitoring topics. "
            "MJ checks these topics once a day and alerts the user when there is a new development. "
            "Use 'add' when the user says 'monitor X', 'track X', 'follow X'. "
            "Use 'remove' when the user says 'stop monitoring X'. "
            "Use 'list' when the user asks what is being monitored. "
            "Do NOT add crypto, financial, or trading topics."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type":        "STRING",
                    "description": "add | remove | list",
                },
                "topic": {
                    "type":        "STRING",
                    "description": "Topic to monitor or stop monitoring (e.g. 'space exploration', 'AI news')",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "openclaw",
        "description": (
            "Delegates complex software tasks, autonomous agent workflows, script execution, "
            "and multi-step system operations to the OpenClaw agent engine. "
            "Call this tool when the user asks to use OpenClaw, run an OpenClaw task, "
            "or perform autonomous sub-agent execution."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task":        {"type": "STRING", "description": "Detailed description of the task for OpenClaw to execute"},
                "action":      {"type": "STRING", "description": "run | status | agent (default: run)"},
                "workspace":   {"type": "STRING", "description": "Optional workspace path for OpenClaw execution"},
            },
            "required": ["task"]
        }
    },
    {
        "name": "restart_mj",
        "description": (
            "Restarts the MJ application itself. Call this when the user says restart yourself, "
            "restart MJ, relaunch yourself, reboot the assistant, apne aap ko restart karo, "
            "or expresses the same intent in any language. Never use shutdown_mj for restart intent."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "shutdown_mj",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop MJ. "
            "The user can say this in ANY language. Never call this when the user asks to restart."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
    "name": "file_processor",
    "description": (
        "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
        "Word docs & text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
        "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
    }
},
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity | preferences | personality | skills | projects | goals | "
                        "relationships | devices | locations | habits | schedule | notes | "
                        "reminders | conversation_summary | semantic_memory | episodic_memory | "
                        "facts | achievements | education | work"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Saksham, pizza, older sister)"},
                "confidence": {"type": "NUMBER", "description": "Confidence from 0 to 1 (default 0.8)"},
                "importance": {"type": "INTEGER", "description": "Long-term importance from 1 to 10 (default 6)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "search_memory",
        "description": (
            "Search the user's long-term memory before answering questions that depend on "
            "their identity, preferences, history, projects, goals, people, devices, schedule, "
            "work, education, or prior conversations. Ignore unrelated results."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "What you need to recall"},
                "category": {"type": "STRING", "description": "Optional memory category"},
                "limit": {"type": "INTEGER", "description": "Maximum results, default 8"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "autopilot",
        "description": (
            "Autonomous vision-guided computer control. Reads the screen with AI and "
            "controls the real mouse and keyboard: locate and click elements, type into "
            "inputs, scroll, press keys, or run a full multi-step task loop that looks, "
            "acts, and verifies until done. Use for: 'open the Downloads folder and rename "
            "report.pdf', 'take control and fill this form', 'click the red button', "
            "'type my address into that box', 'what is on my screen', 'read the text on "
            "screen'. Actions: task (autonomous loop), read (screen reading/OCR), "
            "click (find + click), type (find + type). Stop words: stop, abort, cancel. "
            "Move the mouse to a screen corner to abort immediately."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "task | read | click | type (default: task)"
                },
                "task": {
                    "type": "STRING",
                    "description": "Natural-language task for 'task' action (e.g. 'open Notepad and type Hello World')"
                },
                "description": {
                    "type": "STRING",
                    "description": "What to find on screen (click/type actions), or task fallback for 'task'"
                },
                "text": {
                    "type": "STRING",
                    "description": "Text to type (type action) or question for read action"
                },
                "max_steps": {
                    "type": "INTEGER",
                    "description": "Maximum loop steps 3-25 (default: 12)"
                },
            },
            "required": [],
        },
    },
    {
        "name": "set_emotion",
        "description": (
            "Silently set MJ's simulated response emotion after contextually understanding the user's turn. "
            "Use for emotionally meaningful turns so the avatar, voice, and text style stay aligned. "
            "For serious real problems use caring, serious, or worried; never dramatise or claim real feelings."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "emotion": {"type": "STRING", "enum": list(SUPPORTED_EMOTIONS)},
                "intensity": {"type": "NUMBER", "description": "Strength from 0 to 1"},
                "reason": {"type": "STRING", "description": "Short contextual reason without sensitive inference"},
                "confidence": {"type": "NUMBER", "description": "Classification confidence from 0 to 1"},
            },
            "required": ["emotion", "intensity", "reason"],
        },
    },
]

# --- Plugin system ---


class MJLive:

    def __init__(self, ui: MJUI):
        self.ui             = ui
        self._asst_name     = "MJ"   # updated each session from config
        self.session              = None
        self.audio_in_queue       = None
        self.out_queue            = None
        self._last_assistant_response = ""
        self._loop                = None
        self._is_speaking         = False
        self._speaking_lock       = threading.Lock()
        self._phone_active        = False   # True while phone mic is streaming; pauses PC mic
        self._pending_vision       = None    # (img_bytes, mime_type, question, angle) to inject after tool response
        self._vision_cam_active    = False   # True if camera was opened for vision → auto-close after response
        self._vision_close_pending = False   # True after vision injected; next turn_complete closes camera
        self._vision_last_time     = 0.0     # monotonic time of last screen_process call (cooldown guard)
        self._vision_busy          = False   # True while a vision capture/inject cycle is in flight
        self._interrupted          = False   # True while draining audio after user interrupt
        self.ui.on_text_command   = self._on_text_command
        self.ui.on_remote_clicked = self._make_remote_key
        self.ui.on_interrupt      = self.interrupt
        self.ui.on_voice_interruption_changed = self._set_voice_interruption_enabled
        self._turn_done_event: asyncio.Event | None = None
        self._dashboard     = None
        self._briefing_sent    = False          # morning briefing fires once per process
        self._sys_monitor      = SystemMonitor()  # persistent cooldown state
        self._proactive        = ProactiveEngine()
        self._last_user_speech = time.monotonic()  # updated on every user utterance
        self._session_log: list[str] = []          # conversation turns for end-of-session summary
        self._recent_learned: list[str] = []       # prevents text/transcript double-learning
        self._session_compressing = False
        self._restart_requested = False
        self._speaking_since = 0.0
        self._output_rms = 0.0
        self._ambient_rms = 250.0
        self._voice_interrupt_pending = False
        self._voice_interruption_enabled = get_voice_interruption_enabled()
        self.emotion = EmotionEngine(get_emotion_settings())
        self.personality = FriendPersonalityEngine()
        self._emotion_ai_client = None
        self._last_emotion_preview = ""
        self._emotion_preview_at = 0.0
        self._sleep_inhibitor = SleepInhibitor()
        self._sleep_inhibitor.start_inhibit()
        self._auto_learner = AutonomousLearner()
        self._auto_learner.start()

    def _make_remote_key(self):
        """Called from Qt main thread when user presses Remote Control."""
        if self._dashboard is None:
            self.ui.write_log(
                "SYS: Dashboard unavailable. "
                "Run: pip install fastapi \"uvicorn[standard]\" cryptography"
            )
            return None
        key    = self._dashboard.new_key()
        url    = self._dashboard.get_url()
        manual = self._dashboard.get_manual_url()
        return url, key, f"{url}/auto-login?key={key}", manual

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self._send_user_text(text),
            self._loop
        )

    async def _send_user_text(self, text: str) -> None:
        """Retrieve relevant memory before sending a typed or remote user message."""
        if not self.session:
            print("[MJ] ⚠️ Cannot send text — session not connected.")
            return
        self.ui.write_log(f"You: {text}")
        self.ui.set_state("THINKING")
        await self._analyse_emotion(text, allow_ai=False)
        personality_context = await self._analyse_personality(text, allow_ai=True)
        memory_context, _ = await asyncio.gather(
            asyncio.to_thread(format_relevant_memory_for_prompt, text, 12),
            self._learn_user_message(text),
        )
        emotion_context = self.emotion.getPromptContext()
        personality_context.plan.memory_to_use = re.findall(
            r"(?m)^-\s+([^:]+):", memory_context or ""
        )[:12]
        personality_prompt = self.personality.prompt_context(personality_context)
        contexts = [part for part in (memory_context, personality_prompt, emotion_context) if part]
        memory_count = max(0, memory_context.count("\n- ")) if memory_context else 0
        print(f"[Personality] memories_used={memory_count}")
        context_text = "\n\n".join(contexts)
        payload = f"{context_text}\n\n[USER MESSAGE]\n{text}"
        await self.session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part.from_text(text=payload)],
            ),
            turn_complete=True,
        )

    async def _analyse_emotion(self, text: str, allow_ai: bool = False) -> None:
        state = self.emotion.detectEmotion(text, self._session_log[-12:])
        await self._publish_emotion()
        if not allow_ai or state["confidence"] >= 0.84 or len(text.split()) < 4:
            return
        try:
            if self._emotion_ai_client is None:
                self._emotion_ai_client = genai.Client(api_key=_get_api_key())
            prompt = self.emotion.getAIClassifierPrompt(text, self._session_log[-12:])
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._emotion_ai_client.models.generate_content,
                    model="gemini-3.6-flash",
                    contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": 0.1},
                ),
                timeout=2.5,
            )
            if self.emotion.applyAIResult(response.text or ""):
                await self._publish_emotion()
        except (asyncio.TimeoutError, Exception) as exc:
            print(f"[Emotion] AI refinement skipped: {exc}")

    async def _analyse_personality(self, text: str, allow_ai: bool = False, preview: bool = False):
        context = self.personality.analyse(
            text,
            self._session_log[-12:],
            self.emotion.getCurrentEmotion(),
            learn_preferences=not preview,
        )
        if allow_ai and (
            context.mode.mode in {"honest_advisor", "serious", "debate"}
            or context.claim.agreement_level == "uncertain"
        ):
            try:
                if self._emotion_ai_client is None:
                    self._emotion_ai_client = genai.Client(api_key=_get_api_key())
                prompt = self.personality.get_ai_planner_prompt(text, context, self._session_log[-12:])
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._emotion_ai_client.models.generate_content,
                        model="gemini-3.6-flash",
                        contents=prompt,
                        config={"response_mime_type": "application/json", "temperature": 0.1},
                    ),
                    timeout=2.5,
                )
                context = self.personality.refine_with_ai(context, response.text or "")
            except Exception as exc:
                print(f"[Personality] AI planning fallback used: {type(exc).__name__}")

        self.emotion.updateEmotionState(
            context.plan.mj_emotion,
            self.personality.frontend_payload(context).get("emotion_intensity", 0.45),
            f"conversation mode: {context.mode.mode}",
            context.mode.confidence,
        )
        await self._publish_emotion()
        await self._publish_personality(context)
        print(
            "[Personality] "
            f"mode={context.mode.mode} user_emotion={context.plan.user_emotion} "
            f"mj_emotion={context.plan.mj_emotion} agreement={context.claim.agreement_level} "
            f"safety={context.safety.classification} style={context.response_style['name']} "
            f"avatar={context.avatar['expression']}/{context.avatar['gesture']} "
            f"voice={context.voice['style']}"
        )
        return context

    async def _publish_emotion(self) -> None:
        payload = self.emotion.getFrontendPayload()
        self.ui.set_emotion(payload)
        if self._dashboard:
            await self._dashboard.broadcast({"type": "emotion", **payload})

    async def _publish_personality(self, context=None) -> None:
        payload = self.personality.frontend_payload(context)
        self.ui.set_personality(payload)
        if self._dashboard:
            await self._dashboard.broadcast({"type": "personality", **payload})

    async def _learn_user_message(self, text: str) -> None:
        normalized = re.sub(r"\s+", " ", text).strip().casefold()
        if not normalized or normalized in self._recent_learned:
            return
        self._recent_learned.append(normalized)
        self._recent_learned = self._recent_learned[-20:]
        try:
            learned = await asyncio.to_thread(learnFromConversation, text)
            if learned:
                print(f"[Memory] Learned {len(learned)} durable item(s) from conversation.")
        except Exception as exc:
            print(f"[Memory] Automatic learning skipped: {exc}")

    async def _compress_session_history(self) -> None:
        """Keep long sessions bounded while retaining recent turns verbatim."""
        if self._session_compressing or len(self._session_log) <= 80:
            return
        self._session_compressing = True
        old_count = len(self._session_log) - 30
        old_turns = list(self._session_log[:old_count])
        try:
            summary = await asyncio.to_thread(summarizeConversation, old_turns)
            if summary and len(self._session_log) >= old_count:
                recent = self._session_log[old_count:]
                self._session_log = [f"Earlier conversation summary: {summary}"] + recent
        except Exception as exc:
            print(f"[Memory] Session compression skipped: {exc}")
        finally:
            self._session_compressing = False

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            was_speaking = self._is_speaking
            self._is_speaking = value
            if value and not was_speaking:
                self._speaking_since = time.monotonic()
            elif not value:
                self._output_rms = 0.0
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def _voice_barge_in(self, force: bool = False) -> None:
        """Stop local playback immediately after confident user speech detection."""
        if not self._voice_interruption_enabled:
            self._voice_interrupt_pending = False
            return
        with self._speaking_lock:
            speaking = self._is_speaking
        if not speaking:
            has_buffered_audio = bool(
                self.audio_in_queue and not self.audio_in_queue.empty()
            )
            if not force or not has_buffered_audio:
                self._voice_interrupt_pending = False
                return
        drained = 0
        if self.audio_in_queue:
            while True:
                try:
                    self.audio_in_queue.get_nowait()
                    drained += 1
                except asyncio.QueueEmpty:
                    break
        self.set_speaking(False)
        self.ui.write_log("SYS: Voice interruption detected — listening...")
        print(f"[MJ] Voice barge-in — {drained} queued audio chunks discarded")

    def _set_voice_interruption_enabled(self, enabled: bool) -> None:
        self._voice_interruption_enabled = bool(enabled)
        self._voice_interrupt_pending = False
        print(f"[MJ] Voice interruption {'enabled' if enabled else 'disabled'}")

    def interrupt(self) -> None:
        """Stop MJ mid-speech: drain queued audio and open mic immediately."""
        self._interrupted = True
        q = self.audio_in_queue
        if q:
            drained = 0
            while True:
                try:
                    q.get_nowait()
                    drained += 1
                except Exception:
                    break
            if drained:
                print(f"[MJ] ✋ Interrupted — {drained} audio chunks discarded")
        self.set_speaking(False)
        if self._turn_done_event:
            self._turn_done_event.clear()
        self.ui.write_log("SYS: Interrupted — listening...")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=text)],
                ),
                turn_complete=True,
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        # Load customization from config
        try:
            _cfg = json.loads(open(API_CONFIG_PATH, encoding="utf-8").read())
            self._asst_name = (_cfg.get("assistant_name") or "MJ").strip()
            _user_name = (_cfg.get("user_name") or "").strip()
            _voice_gender = (_cfg.get("tts_voice_gender") or "female").strip().lower()
        except Exception:
            self._asst_name = "MJ"
            _user_name = ""
            _voice_gender = "female"

        _live_voice = "Aoede" if _voice_gender == "female" else "Charon"

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        # Identity injection — overrides any hardcoded name in prompt.txt
        _addr = (f"ADDRESS: Always call the user '{_user_name}'."
                 if _user_name
                 else "ADDRESS: Match the user's language naturally. Hinglish is allowed and preferred "
                      "for casual Hindi-English conversation. Use bro/bhai sparingly when it fits.")
        identity_ctx = (
            f"[IDENTITY]\n"
            f"Your name is {self._asst_name}. "
            f"Always refer to yourself as {self._asst_name}.\n"
            f"{_addr}\n\n"
        )

        parts = [time_ctx, identity_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)
        parts.append(
            "[EMOTION PROTOCOL]\n"
            "Use set_emotion silently for emotionally meaningful user turns before responding. "
            "Emotion is a simulated presentation style, not a claim of real feelings. "
            "Keep transitions natural, remain respectful, and never manipulate or exaggerate serious situations."
        )
        personality_prompt = self.personality.system_prompt()
        if personality_prompt:
            parts.append(personality_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            enable_affective_dialog=True,
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    prefix_padding_ms=150,
                    silence_duration_ms=500,
                ),
                activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=_live_voice
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[MJ] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        if name == "set_emotion":
            state = self.emotion.updateEmotionState(
                str(args.get("emotion", "neutral")).lower(),
                float(args.get("intensity", 0.5)),
                str(args.get("reason", "contextual model decision")),
                float(args.get("confidence", 0.75)),
            )
            await self._publish_emotion()
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={
                    "result": "emotion style applied",
                    "state": state,
                    "response_style": self.emotion.getEmotionResponseStyle(),
                    "silent": True,
                },
            )

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {
                    "value": value,
                    "confidence": args.get("confidence", 0.85),
                    "importance": args.get("importance", 7),
                    "source": "gemini_tool",
                }}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        if name == "search_memory":
            query = args.get("query", "")
            category = args.get("category") or None
            limit = max(1, min(20, int(args.get("limit", 8))))
            matches = await asyncio.to_thread(
                searchMemory, query, category, None, None, 1, False, True, limit
            )
            compact = [
                {
                    "category": item["category"],
                    "key": item["key"],
                    "value": item["value"],
                    "confidence": item["confidence"],
                    "relevance": item["relevance"],
                }
                for item in matches
            ]
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": compact or "No relevant long-term memory found."},
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "screen_process":
                import time as _t_mod
                _now = _t_mod.monotonic()
                _cooldown = 4.0  # seconds — covers echo window after speaking ends
                if self._vision_busy or (_now - self._vision_last_time) < _cooldown:
                    _wait = max(0, _cooldown - (_now - self._vision_last_time))
                    print(f"[Vision] ⏳ Cooldown active ({_wait:.1f}s remaining) — ignoring duplicate call")
                    result = "Vision is still processing the previous request. I will not call this again."
                else:
                    self._vision_busy      = True
                    self._vision_last_time = _now
                    angle     = args.get("angle", "screen").lower()
                    user_text = args.get("text", "What do you see?")
                    if angle == "camera":
                        img_b, mime_t = await loop.run_in_executor(None, _capture_camera)
                        self.ui.start_camera_stream()
                        self._vision_cam_active = True
                        print(f"[Vision] 📷 Camera: {len(img_b):,} bytes")
                        _stall = "camera"
                    else:
                        img_b, mime_t = await loop.run_in_executor(None, _capture_screen)
                        print(f"[Vision] 🖥️  Screen: {len(img_b):,} bytes")
                        _stall = "screen"
                    self._pending_vision = (img_b, mime_t, user_text, angle)
                    result = (
                        f"[VISION_ACTIVE] {_stall.capitalize()} captured. "
                        f"Immediately say ONE short natural sentence in the user's own language, "
                        f"telling them you are looking at their {_stall} right now. "
                        f"Do NOT describe or guess content — the actual image arrives in the NEXT message."
                    )

            elif name == "close_camera":
                self.ui.stop_camera_stream()
                result = "Camera closed."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "show_last_photo":
                result = show_last_camera_photo(player=self.ui)

            elif name == "take_photo":
                r = await loop.run_in_executor(None, lambda: take_photo(player=self.ui))
                result = r or "Photo clicked."

            elif name == "self_edit":
                file_path = str(args.get("file_path", "")).strip()
                content = args.get("content", "")
                if not file_path:
                    result = "No file_path provided."
                elif content is None:
                    result = "No content provided."
                else:
                    result = await loop.run_in_executor(
                        None,
                        lambda: self_edit_file(target_relative_path=file_path, new_content=content)
                    )

            elif name == "neural_status":
                brain = get_neural_brain()
                status = brain.get_status()
                result = json.dumps(status, indent=2)

            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "ponytail":
                r = await loop.run_in_executor(None, lambda: ponytail_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "slopwatch":
                r = await loop.run_in_executor(None, lambda: slopwatch_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "whatsapp":
                r = await loop.run_in_executor(None, lambda: whatsapp_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "notes_memo":
                r = await loop.run_in_executor(None, lambda: notes_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "system_optimizer":
                r = await loop.run_in_executor(None, lambda: system_optimizer(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "terminal_control":
                action = str(args.get("action", "toggle")).lower().strip()
                cmd = str(args.get("command", "")).strip()
                if self.ui and hasattr(self.ui, "toggle_terminal"):
                    if action == "open":
                        self.ui.show_terminal(cmd)
                        result = f"Terminal opened{' and executed: ' + cmd if cmd else ''}."
                    elif action == "close":
                        self.ui._terminal_panel.hide()
                        result = "Terminal closed."
                    elif action == "clear":
                        self.ui._clear_terminal()
                        result = "Terminal cleared."
                    elif action == "run" and cmd:
                        self.ui.show_terminal(cmd)
                        result = f"Command '{cmd}' executed in terminal."
                    else:
                        self.ui.toggle_terminal()
                        result = "Terminal toggled."
                else:
                    result = "UI Terminal not available."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "openclaw":
                r = await loop.run_in_executor(None, lambda: openclaw_task(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."
                # Mirror results to the on-screen content panel
                _mode = args.get("mode", "search")
                if r and not r.startswith("No results") and not r.startswith("Search failed"):
                    _query = args.get("query") or ", ".join(args.get("items", []))
                    _label = f"{_mode.upper()} — {_query[:38]}" if _query else _mode.upper()
                    self.ui.show_content(_label, r)
            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(
                    None,
                    lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "autopilot":
                r = await loop.run_in_executor(None, lambda: autopilot_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Autopilot finished."

            elif name == "system_status":
                r = await loop.run_in_executor(None, get_system_status)
                result = str(r)

            elif name == "manage_monitor":
                action = args.get("action", "").lower().strip()
                topic  = args.get("topic", "").strip()
                if action == "add" and topic:
                    result = await asyncio.to_thread(add_monitor, topic)
                elif action == "remove" and topic:
                    result = await asyncio.to_thread(remove_monitor, topic)
                elif action == "list":
                    topics = await asyncio.to_thread(list_monitors)
                    result = ("Monitoring: " + ", ".join(topics)) if topics else "No topics are being monitored."
                else:
                    result = "Specify action (add/remove/list) and a topic."

            elif name == "shutdown_mj":
                self.ui.write_log("SYS: Shutdown requested.")
                async def _do_shutdown():
                    await self._save_session_summary()
                    if self.session:
                        try:
                            await self.session.send_client_content(
                                turns=types.Content(
                                    role="user",
                                    parts=[types.Part.from_text(text="Say a brief natural goodbye to the user.")],
                                ),
                                turn_complete=True,
                            )
                        except Exception:
                            pass
                    await asyncio.sleep(1.5)
                    import os as _os
                    _os._exit(0)
                asyncio.create_task(_do_shutdown())

            elif name == "restart_mj":
                if self._restart_requested:
                    result = "MJ restart is already in progress."
                else:
                    self._restart_requested = True
                    self.ui.write_log("SYS: Restart requested.")
                    if self._turn_done_event:
                        self._turn_done_event.clear()

                    async def _do_restart():
                        await self._save_session_summary()
                        if self._turn_done_event:
                            try:
                                await asyncio.wait_for(
                                    self._turn_done_event.wait(), timeout=4.0
                                )
                            except asyncio.TimeoutError:
                                pass
                        else:
                            await asyncio.sleep(1.5)
                        await asyncio.sleep(0.3)
                        try:
                            _subprocess.Popen(
                                _restart_command(),
                                cwd=str(BASE_DIR),
                                close_fds=True,
                            )
                        except Exception as exc:
                            self._restart_requested = False
                            self.ui.write_log(f"ERR: Restart failed — {exc}")
                            print(f"[MJ] Restart failed: {exc}")
                            return
                        await asyncio.sleep(0.2)
                        import os as _os
                        _os._exit(0)

                    asyncio.create_task(_do_restart())
                    result = "Restart initiated."

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[MJ] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            # Native-audio models need the PCM sample rate in the MIME type.
            # Bare ``audio/pcm`` can leave VAD receiving undecodable frames even
            # though both the microphone and websocket appear to be healthy.
            await self.session.send_realtime_input(
                audio=types.Blob(data=msg, mime_type=INPUT_AUDIO_MIME)
            )

    async def _listen_audio(self):
        print("[MJ] 🎤 Mic started")
        loop = asyncio.get_event_loop()
        pre_roll: deque[bytes] = deque(maxlen=5)
        hot_frames = 0

        def queue_audio(data: bytes) -> None:
            try:
                self.out_queue.put_nowait(data)
            except asyncio.QueueFull:
                pass

        def callback(indata, frames, time_info, status):
            nonlocal hot_frames
            if self.ui.muted or self._phone_active:
                pre_roll.clear()
                hot_frames = 0
                return

            data = indata.tobytes()
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            mic_rms = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0
            with self._speaking_lock:
                mj_speaking = self._is_speaking

            if mj_speaking and not self._voice_interruption_enabled:
                pre_roll.clear()
                hot_frames = 0
                self._voice_interrupt_pending = False
                return

            if not mj_speaking:
                self._ambient_rms = 0.98 * self._ambient_rms + 0.02 * mic_rms
                pre_roll.clear()
                hot_frames = 0
                self._voice_interrupt_pending = False
                loop.call_soon_threadsafe(queue_audio, data)
                return

            pre_roll.append(data)
            if time.monotonic() - self._speaking_since < 0.35:
                return

            # Speaker echo is normally a fraction of the original output level.
            # Require sustained input above both ambient noise and echo reference.
            threshold = _barge_in_threshold(self._ambient_rms, self._output_rms)
            hot_frames = hot_frames + 1 if mic_rms >= threshold else 0
            if hot_frames < 2:
                return

            if not self._voice_interrupt_pending:
                self._voice_interrupt_pending = True
                loop.call_soon_threadsafe(self._voice_barge_in)
                for buffered in pre_roll:
                    loop.call_soon_threadsafe(queue_audio, buffered)
            else:
                loop.call_soon_threadsafe(queue_audio, data)

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                print("[MJ] 🎤 Mic stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[MJ] ❌ Mic: {e}")
            raise

    async def _receive_audio(self):
        print("[MJ] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        if self._interrupted:
                            pass  # discard: interrupted
                        else:
                            if self._turn_done_event and self._turn_done_event.is_set():
                                self._turn_done_event.clear()
                            # Split into ~50 ms chunks so interrupt() stops audio within 50 ms
                            # (24000 Hz × 2 bytes/sample × 0.05 s = 2400 bytes per slice)
                            _audio_data = response.data
                            _SLICE = 2400
                            for _i in range(0, len(_audio_data), _SLICE):
                                self.audio_in_queue.put_nowait(_audio_data[_i : _i + _SLICE])

                    if response.server_content:
                        sc = response.server_content

                        if sc.interrupted:
                            # Gemini confirmed user activity. Ensure no already-buffered
                            # assistant audio continues playing after the interruption.
                            self._voice_barge_in(force=True)
                            self._voice_interrupt_pending = False
                            out_buf = []

                        if (
                            not sc.interrupted
                            and sc.output_transcription
                            and sc.output_transcription.text
                        ):
                            _append_output_transcript(out_buf, sc.output_transcription.text)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)
                                self._last_user_speech = time.monotonic()
                                preview = " ".join(in_buf).strip()
                                now = time.monotonic()
                                if (
                                    len(preview.split()) >= 3
                                    and preview != self._last_emotion_preview
                                    and now - self._emotion_preview_at >= 0.4
                                ):
                                    self.emotion.previewEmotion(preview, self._session_log[-12:])
                                    self._last_emotion_preview = preview
                                    self._emotion_preview_at = now
                                    await self._publish_emotion()
                                    await self._analyse_personality(preview, allow_ai=False, preview=True)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            # If this turn_complete ends an interrupted response, clear the
                            # flag and skip all further processing for that turn.
                            if self._interrupted:
                                self._interrupted = False
                                in_buf  = []
                                out_buf = []
                                continue

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                await self._analyse_emotion(full_in, allow_ai=False)
                                await self._analyse_personality(full_in, allow_ai=False)
                                self.ui.write_log(f"You: {full_in}")
                                self._session_log.append(f"User: {full_in}")
                                asyncio.create_task(self._learn_user_message(full_in))
                                if self._dashboard:
                                    asyncio.create_task(self._dashboard.broadcast({
                                        "type": "log", "speaker": "user",
                                        "text": full_in,
                                        "ts": datetime.now().isoformat(),
                                    }))
                            in_buf = []
                            self._last_emotion_preview = ""

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                if full_out == self._last_assistant_response:
                                    print("[MJ] Duplicate assistant response suppressed")
                                else:
                                    self._last_assistant_response = full_out
                                    self.ui.write_log(f"{self._asst_name}: {full_out}")
                                    self._session_log.append(f"{self._asst_name}: {full_out}")
                                    if self._dashboard:
                                        personality_payload = self.personality.frontend_payload()
                                        emotion_state = self.emotion.getCurrentEmotion()
                                        emotion_voice = self.emotion.getVoiceEmotionSettings()
                                        avatar = dict(personality_payload.get("avatar", {}))
                                        avatar["state"] = "speaking"
                                        voice = dict(personality_payload.get("voice", {}))
                                        voice.update({
                                            "speed": emotion_voice["speed"],
                                            "pitch": emotion_voice["pitch"],
                                            "style": emotion_voice["voice_style"],
                                        })
                                        asyncio.create_task(self._dashboard.broadcast({
                                            "type": "assistant_response", "speaker": "mj",
                                            "text": full_out,
                                            "conversation_mode": personality_payload.get("conversation_mode", "casual_friend"),
                                            "emotion": {
                                                "name": emotion_state["current_emotion"],
                                                "intensity": emotion_state["intensity"],
                                            },
                                            "avatar": avatar,
                                            "voice": voice,
                                            "ts": datetime.now().isoformat(),
                                        }))
                                    truth_warnings = self.personality.review_response(full_out)
                                    if truth_warnings:
                                        print(f"[Personality] response_guard={','.join(truth_warnings)}")
                            out_buf = []
                            if len(self._session_log) > 80:
                                asyncio.create_task(self._compress_session_history())

                            # Vision injection: model finished tool-response turn → now send the image
                            if self._pending_vision and self.session:
                                import base64 as _b64
                                img_b, mime_t, question, angle = self._pending_vision
                                self._pending_vision = None
                                b64 = _b64.b64encode(img_b).decode("ascii")
                                print(f"[Vision] 📤 {len(img_b):,} bytes (angle={angle}) → main session")
                                await self.session.send_client_content(
                                    turns=types.Content(
                                        role="user",
                                        parts=[
                                            types.Part.from_bytes(data=img_b, mime_type=mime_t),
                                            types.Part.from_text(text=question),
                                        ],
                                    ),
                                    turn_complete=True,
                                )
                                # Mark next turn_complete behaviour depending on angle
                                if self._vision_cam_active:
                                    # Camera: keep busy until MJ finishes speaking the answer
                                    self._vision_cam_active    = False
                                    self._vision_close_pending = True
                                else:
                                    # Screen-only: no camera to close; release busy flag now
                                    self._vision_busy = False
                            elif self._vision_close_pending:
                                # This turn_complete IS the vision answer — close camera + release busy flag
                                self._vision_close_pending = False
                                self._vision_busy = False
                                async def _cam_close():
                                    await asyncio.sleep(2.0)
                                    self.ui.stop_camera_stream()
                                asyncio.create_task(_cam_close())

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[MJ] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except Exception as e:
            print(f"[MJ] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[MJ] 🔊 Play started")

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue

                self.set_speaking(True)

                # Batch all immediately-available chunks into one write to reduce
                # thread-pool round-trips (was one asyncio.to_thread per 50ms slice).
                # Cap at ~200 ms so interrupt() still stops audio within ~200 ms.
                batch = bytearray(chunk)
                while len(batch) < 9600:   # 9600 bytes ≈ 200 ms at 24 kHz / 16-bit mono
                    try:
                        batch.extend(self.audio_in_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                try:
                    voice_settings = self.emotion.getVoiceEmotionSettings()
                    styled_batch = apply_pcm16_settings(bytes(batch), voice_settings)
                    samples = np.frombuffer(styled_batch, dtype=np.int16).astype(np.float32)
                    if samples.size:
                        self._output_rms = float(np.sqrt(np.mean(samples * samples)))
                    await asyncio.to_thread(stream.write, styled_batch)
                except (RuntimeError, asyncio.CancelledError):
                    break   # executor shutting down — exit cleanly
        except Exception as e:
            print(f"[MJ] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    # ── Morning briefing ────────────────────────────────────────────────────────

    async def _send_startup_briefing(self) -> None:
        """
        Two-phase briefing optimized for speed:
          Phase 1 — instant greeting (no tools) → speech starts in <1s
          Phase 2 — news pre-fetched in a background thread while Phase 1 plays,
                    delivered as ready text (no Gemini tool-call round-trip) and
                    shown on the UI content panel. Waits for turn_complete event
                    instead of a fixed sleep so there is no unnecessary gap.
        """
        memory   = load_memory()
        identity = memory.get("identity", {})

        def _val(k: str) -> str:
            e = identity.get(k, {})
            return (e.get("value", "") if isinstance(e, dict) else str(e)).strip()

        lang = _val("language")
        name = _val("name")
        time_str = datetime.now().strftime("%H:%M")

        # Start fetching news immediately — runs in parallel while phase 1 plays
        loop = asyncio.get_event_loop()
        news_future = loop.run_in_executor(None, _fetch_news_sync, "top world news today")

        await asyncio.sleep(0.3)
        if not self.session:
            return

        # ── Phase 1: instant greeting ─────────────────────────────────────────
        lang_clause = f" Respond in {lang}." if lang else ""
        name_clause = f" Address the user as {name}." if name else ""

        # Inject last session context if available — pop removes it so it's never repeated
        last = await asyncio.to_thread(pop_last_session)
        session_clause = ""
        if last:
            try:
                _delta = (datetime.now() - datetime.strptime(last["date"], "%Y-%m-%d")).days
                _when  = "earlier today" if _delta == 0 else ("yesterday" if _delta == 1 else f"{_delta} days ago")
            except Exception:
                _when = "last time"
            session_clause = (
                f" Also briefly and naturally mention that {_when}: {last['summary']}"
            )

        p1 = (
            f"Greet the user warmly, mention it is {time_str}, and say you are fetching today's news now.{session_clause} "
            f"Keep it to 2 short sentences max. Do not call any tools.{lang_clause}{name_clause}"
        )

        # Clear the turn-done event so we can wait for Phase 1 to finish
        if self._turn_done_event:
            self._turn_done_event.clear()

        await self.session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part.from_text(text=p1)],
            ),
            turn_complete=True,
        )
        self.ui.write_log("SYS: Briefing phase 1 (greeting) sent.")

        # ── Phase 2: fire as soon as Phase 1 audio is done ───────────────────
        async def _deliver_news():
            try:
                lang_str = f" Respond in {lang}." if lang else ""

                # Wait for news fetch (already running) and Phase 1 turn-complete
                # in parallel — whichever takes longer determines the wait time
                news_done   = asyncio.wrap_future(news_future)
                turn_waited = False
                if self._turn_done_event:
                    try:
                        await asyncio.wait_for(self._turn_done_event.wait(), timeout=6.0)
                        turn_waited = True
                    except asyncio.TimeoutError:
                        pass

                # Extra buffer: turn_complete fires when Gemini finishes *generating*
                # Phase 1, but audio may still be playing.  Waiting a beat here
                # prevents Phase 2 audio from arriving while Phase 1 is mid-sentence
                # (which sounds like a "repeated first response" to the user).
                if turn_waited:
                    await asyncio.sleep(0.8)
                else:
                    await asyncio.sleep(1.0)

                try:
                    news_text = await asyncio.wait_for(news_done, timeout=4.0)
                except Exception:
                    news_text = ""

                if not self.session:
                    return

                if news_text and len(news_text) > 60:
                    # Show on UI content panel immediately
                    self.ui.show_content("NEWS — top world news today", news_text)

                    p2 = (
                        f"[BRIEFING] Here are today's top news headlines:\n{news_text}\n\n"
                        "Pick ONE headline, summarise it in one sentence, then say the full list "
                        f"is displayed on screen. Do not call any tools.{lang_str}"
                    )
                else:
                    p2 = (
                        "News headlines could not be fetched right now. "
                        f"Let the user know briefly.{lang_str}"
                    )

                await self.session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=p2)],
                    ),
                    turn_complete=True,
                )
                self.ui.write_log("SYS: Briefing phase 2 (news) sent.")
            except Exception as e:
                print(f"[Briefing] Phase 2 error: {e}")
                self.ui.write_log(f"SYS: Briefing phase 2 failed: {e}")

        asyncio.create_task(_deliver_news())

    # ── Session memory ──────────────────────────────────────────────────────────

    async def _save_session_summary(self) -> None:
        """Summarise the current session in 1-2 sentences and save to long_term.json."""
        log = self._session_log
        if len(log) < 3:          # need at least one exchange to be worth saving
            return

        memory = load_memory()
        lang_entry = memory.get("identity", {}).get("language", {})
        lang = (lang_entry.get("value", "") if isinstance(lang_entry, dict) else str(lang_entry)).strip()
        lang = lang or "English"

        convo = "\n".join(log[-40:])   # cap at last 40 turns to stay within token budget
        prompt = (
            f"Summarize this conversation in 1-2 sentences in {lang}. "
            "Focus on what the user accomplished or discussed. "
            "Output ONLY the summary text, nothing else:\n\n" + convo
        )
        summary = ""
        try:
            from google import genai as _genai
            client = _genai.Client(api_key=_get_api_key())
            resp   = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-3.6-flash",
                contents=prompt,
            )
            summary = (resp.text or "").strip()
        except Exception as e:
            print(f"[Memory] ⚠️ Session summary failed: {e}")

        if not summary:
            # Fallback: preserve the actual last exchange if model summarization fails.
            cleaned = re.sub(r"\s+", " ", convo.replace("\n", " ")).strip()
            summary = cleaned[:400].strip()
            if len(cleaned) > 400:
                summary = summary.rsplit(" ", 1)[0] + "..."
            summary = f"Last conversation: {summary}"

        save_session_summary(summary, lang)
        self._session_log = []    # reset only after persistence succeeds

    # ── System monitor ──────────────────────────────────────────────────────────

    async def _run_system_monitor(self) -> None:
        """Background task: voice alerts when metrics exceed thresholds."""
        while True:
            await asyncio.sleep(10)
            alert = await asyncio.to_thread(self._sys_monitor.check)
            if not alert or not self.session:
                continue
            # Don't interrupt an active conversation
            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking or (time.monotonic() - self._last_user_speech) < 10:
                continue
            try:
                await self.session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=alert)],
                    ),
                    turn_complete=True,
                )
            except Exception as e:
                print(f"[Monitor] ⚠️ Could not send alert: {e}")

    # ── Background monitor ──────────────────────────────────────────────────────

    async def _run_background_monitor(self) -> None:
        """Check user-configured topics once per day; speak alerts when new headlines appear."""
        await asyncio.sleep(300)          # wait 5 min after startup before first check
        while True:
            if self.session:
                # Don't interrupt if user spoke recently or MJ is mid-sentence
                with self._speaking_lock:
                    speaking = self._is_speaking
                recent_speech = (time.monotonic() - self._last_user_speech) < 30
                if not speaking and not recent_speech:
                    try:
                        alerts = await asyncio.to_thread(monitor_check_all)
                        memory = load_memory()
                        lang_e = memory.get("identity", {}).get("language", {})
                        lang   = (lang_e.get("value", "") if isinstance(lang_e, dict) else str(lang_e)).strip() or "English"
                        for alert in alerts:
                            msg = (
                                f"{alert}\n\n"
                                f"Inform the user about this development naturally in {lang}. "
                                "One brief sentence only."
                            )
                            await self.session.send_client_content(
                                turns=types.Content(
                                    role="user",
                                    parts=[types.Part.from_text(text=msg)],
                                ),
                                turn_complete=True,
                            )
                            self.ui.write_log(f"SYS: Monitor alert sent.")
                            await asyncio.sleep(6)   # gap between consecutive alerts
                    except Exception as e:
                        print(f"[Monitor] ⚠️ Background check error: {e}")
            await asyncio.sleep(1800)     # check every 30 minutes

    # ── Proactive mode ──────────────────────────────────────────────────────────

    async def _run_proactive_mode(self) -> None:
        """
        Background task: periodically checks if the user has been silent long enough,
        then hands time + memory context to Gemini so it can decide what (if anything)
        to say proactively. No hardcoded rules — Gemini makes the call.
        """
        while True:
            await asyncio.sleep(60)   # evaluate once per minute

            if not self.session:
                continue

            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking:
                continue

            if not self._proactive.should_trigger(self._last_user_speech):
                continue

            self._proactive.mark_triggered()

            try:
                memory       = await asyncio.to_thread(load_memory)
                monitors     = await asyncio.to_thread(list_monitors)
                recent_turns = self._session_log[-8:] if self._session_log else []
                prompt = self._proactive.build_prompt(
                    memory       = memory,
                    monitors     = monitors or None,
                    recent_turns = recent_turns or None,
                )
                await self.session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)],
                    ),
                    turn_complete=True,
                )
                self.ui.write_log("SYS: Proactive check-in.")
            except Exception as e:
                print(f"[Proactive] ⚠️ {e}")

    async def _run_memory_maintenance(self) -> None:
        """Archive expired or obsolete memories without blocking live audio."""
        await asyncio.sleep(30)
        while True:
            try:
                result = await asyncio.to_thread(cleanupMemory)
                if any(result.values()):
                    print(f"[Memory] Automatic cleanup: {result}")
            except Exception as exc:
                print(f"[Memory] Maintenance skipped: {exc}")
            await asyncio.sleep(21600)

    async def _run_emotion_decay(self) -> None:
        """Gradually settle transient expression state without persisting it."""
        while True:
            await asyncio.sleep(max(5, int(self.emotion.settings["emotion_decay_time"]) // 6))
            before = self.emotion.getCurrentEmotion()
            after = self.emotion.decayEmotion()
            if (before["current_emotion"], before["intensity"]) != (after["current_emotion"], after["intensity"]):
                await self._publish_emotion()

    # ── Phone audio relay ────────────────────────────────────────────────────────

    async def _relay_phone_audio(self) -> None:
        """Forward phone mic PCM chunks from dashboard queue into the Gemini Live session."""
        q = self._dashboard._phone_audio_queue
        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # No audio for 1 s → phone mic inactive, give PC mic back
                self._phone_active = False
                continue
            self._phone_active = True   # phone is streaming — silence PC mic
            if not self.ui.muted:
                with self._speaking_lock:
                    speaking = self._is_speaking
                if speaking and not self._voice_interruption_enabled:
                    continue
                try:
                    self.out_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass

    def _on_phone_connected(self) -> None:
        self.ui.write_log("SYS: Phone connected via Remote Dashboard.")
        self.ui.notify_phone_connected()

    # ── dashboard command relay ─────────────────────────────────────────────

    async def _process_dashboard_commands(self) -> None:
        while True:
            try:
                text = await asyncio.wait_for(
                    self._dashboard._command_queue.get(), timeout=0.5
                )
                if not text:
                    continue
                # Wait up to 8s for session to become ready after a wake
                for _ in range(80):
                    if self.session:
                        break
                    await asyncio.sleep(0.1)
                if self.session:
                    await self._send_user_text(text)
                    self.ui.write_log(f"[Web]: {text}")
                else:
                    print(f"[Dashboard] Dropped command (no session): {text}")
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"[Dashboard] Command error: {e}")
                await asyncio.sleep(0.5)

    # ── main loop ───────────────────────────────────────────────────────────

    async def run(self):
        self._loop = asyncio.get_event_loop()

        # Start dashboard (optional — needs: pip install fastapi "uvicorn[standard]" cryptography)
        try:
            from dashboard.server import DashboardServer
            self._dashboard = DashboardServer()
            self._dashboard.set_connect_callback(self._on_phone_connected)
            asyncio.create_task(self._dashboard.serve())
            # Runs for the whole lifetime, not just inside an active session
            asyncio.create_task(self._process_dashboard_commands())
        except Exception as e:
            print(f"[Dashboard] Disabled: {e}")
            self._dashboard = None

        while True:
            try:
                print("[MJ] Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                # Fresh client on every reconnect — avoids stale HTTP session state
                client = genai.Client(
                    api_key=_get_api_key(),
                    http_options={"api_version": "v1beta"}
                )

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session          = session
                    self.audio_in_queue   = asyncio.Queue()
                    self.out_queue        = asyncio.Queue(maxsize=200)
                    self._turn_done_event = asyncio.Event()

                    # Reset transient state that must not carry over from a previous session
                    self._pending_vision           = None
                    self._vision_cam_active        = False
                    self._vision_close_pending     = False
                    self._vision_busy              = False
                    self._vision_last_time         = 0.0
                    self._interrupted              = False
                    self._last_assistant_response  = ""

                    print("[MJ] Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: MJ online.")
                    await self._publish_emotion()
                    await self._publish_personality()

                    if self._dashboard:
                        await self._dashboard.broadcast({"type": "status", "state": "active"})

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    tg.create_task(self._run_system_monitor())
                    tg.create_task(self._run_background_monitor())
                    tg.create_task(self._run_proactive_mode())
                    tg.create_task(self._run_memory_maintenance())
                    tg.create_task(self._run_emotion_decay())
                    if self._dashboard:
                        tg.create_task(self._relay_phone_audio())

                    # Morning briefing — fires once per process launch (if enabled)
                    if not self._briefing_sent and get_brief_enabled():
                        self._briefing_sent = True
                        tg.create_task(self._send_startup_briefing())

            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except BaseException as e:
                # Catches both Exception and BaseExceptionGroup (Python 3.11+
                # TaskGroup raises BaseExceptionGroup when tasks are cancelled
                # externally, which `except Exception` would miss, letting the
                # exception escape the while-loop and causing asyncio.run() to
                # start shutdown — resulting in "executor after shutdown" errors).
                err_str = str(e)
                print(f"[MJ] Error ({type(e).__name__}): {e}")
                traceback.print_exc()

                # Invalid API key — stop hammering the API, prompt re-configuration
                if "API key not valid" in err_str or "1007" in err_str:
                    self.ui.write_log("ERR: API key invalid — please re-enter your key.")
                    self.ui.set_state("SLEEPING")
                    self.ui.prompt_reconfig()
                    while not self.ui._win._ready:
                        await asyncio.sleep(1)
                    print("[MJ] New API key saved — reconnecting...")
                    _conn_backoff = 3
                    continue

                # Network / timeout errors — log clearly and back off
                is_net_err = any(k in err_str for k in (
                    "TimeoutError", "timed out", "getaddrinfo", "CancelledError",
                    "ConnectionRefusedError", "OSError", "Cannot connect",
                ))
                if is_net_err:
                    _conn_backoff = min(getattr(self, "_conn_backoff", 3) * 2, 60)
                    self._conn_backoff = _conn_backoff
                    self.ui.write_log(
                        f"NET: Connection failed — retrying in {_conn_backoff}s. "
                        "(Check internet / API key)"
                    )
                else:
                    self._conn_backoff = 3
            finally:
                self.session = None
                # Only save if there was a real conversation (≥3 turns)
                if len(self._session_log) >= 3:
                    asyncio.create_task(self._save_session_summary())

            self.set_speaking(False)
            self.ui.set_state("SLEEPING")

            if self._dashboard:
                await self._dashboard.broadcast({"type": "status", "state": "sleeping"})

            delay = getattr(self, "_conn_backoff", 3)
            print(f"[MJ] Reconnecting in {delay}s...")
            await asyncio.sleep(delay)

def main():
    configured_face = BASE_DIR / "config" / "mj.png"
    if not configured_face.exists():
        configured_face = BASE_DIR / "config" / "mj.png"
    face_path = configured_face if configured_face.exists() else BASE_DIR / "face.png"
    ui = MJUI(str(face_path))

    def runner():
        ui.wait_for_api_key()
        mj = MJLive(ui)
        try:
            asyncio.run(mj.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

if __name__ == "__main__":
    main()
