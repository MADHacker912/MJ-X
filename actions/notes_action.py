"""
actions/notes_action.py — Smart Notes, Memos & Quick Memory for MJ.
===================================================================
Allows MJ to take notes, save ideas, create todo lists, and search notes.
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _base_dir()
NOTES_FILE = BASE_DIR / "memory" / "user_notes.json"


def _load_notes() -> List[Dict[str, Any]]:
    if NOTES_FILE.exists():
        try:
            data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _save_notes(notes: List[Dict[str, Any]]):
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    NOTES_FILE.write_text(json.dumps(notes, indent=2), encoding="utf-8")


def notes_action(parameters: dict, player=None, speak=None) -> str:
    """
    Dispatches Notes commands:
    - add: Save note/idea (params: text, category)
    - list: View all notes
    - search: Search notes by keyword (param: query)
    - delete: Delete note by index or keyword (param: id or query)
    - clear: Delete all notes
    """
    action = str(parameters.get("action", "list")).lower().strip()
    text = str(parameters.get("text", "") or parameters.get("note", "") or parameters.get("content", "")).strip()
    category = str(parameters.get("category", "General")).strip()
    query = str(parameters.get("query", "") or parameters.get("search", "") or text).strip()

    notes = _load_notes()

    # 1. Add Note
    if action in ("add", "create", "write", "save", "take_note"):
        if not text:
            return "Error: Note content cannot be empty."
        new_id = len(notes) + 1
        note_entry = {
            "id": new_id,
            "text": text,
            "category": category.title(),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": int(time.time()),
        }
        notes.append(note_entry)
        _save_notes(notes)
        res = f"📝 Note saved #{new_id} [{note_entry['category']}]: \"{text}\""
        if player and hasattr(player, "append_log"):
            player.append_log(f"SYS: {res}")
        return res

    # 2. List Notes
    elif action in ("list", "all", "show", "view", "get"):
        if not notes:
            return "No notes found in memory. You can say 'MJ, take note: ...' to save one."

        lines = [f"📋 Saved Notes ({len(notes)}):"]
        for idx, n in enumerate(notes, 1):
            lines.append(f"{idx}. [{n.get('category', 'General')}] {n.get('text')}  _(Created: {n.get('created_at', '')[-8:]})_")
        res = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("MY NOTES", res)
        return res

    # 3. Search Notes
    elif action in ("search", "find", "filter"):
        if not query:
            return "Please specify what note or keyword you want to search."
        matched = [n for n in notes if query.lower() in n.get("text", "").lower() or query.lower() in n.get("category", "").lower()]
        if not matched:
            return f"No notes matching '{query}' were found."

        lines = [f"🔍 Search Results for '{query}' ({len(matched)}):"]
        for n in matched:
            lines.append(f"• [{n.get('category')}] {n.get('text')} (Date: {n.get('created_at', '')})")
        res = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("NOTE SEARCH", res)
        return res

    # 4. Delete Note
    elif action in ("delete", "remove"):
        if not query and not parameters.get("id"):
            return "Please specify the note number or text to delete."

        target_id = parameters.get("id")
        initial_len = len(notes)
        if target_id is not None:
            try:
                tid = int(target_id)
                notes = [n for n in notes if n.get("id") != tid]
            except ValueError:
                pass
        else:
            notes = [n for n in notes if query.lower() not in n.get("text", "").lower()]

        if len(notes) < initial_len:
            _save_notes(notes)
            return f"✅ Deleted matching note(s). Remaining: {len(notes)} notes."
        return "No matching note found to delete."

    # 5. Clear All
    elif action == "clear":
        _save_notes([])
        return "🧹 All notes cleared."

    return "Available notes actions: add (text='...') | list | search (query='...') | delete | clear"
