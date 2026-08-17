"""
bridges/whatsapp_bridge.py — WhatsApp Integration Bridge for MJ AI Assistant.
=============================================================================
Connects MJ to WhatsApp using a local Baileys Multi-Device Gateway server.
Tracks sender names, numbers, conversation history, and unread messages.
Replies with customized assistant persona and allows checking recent messages & sending.
"""

import os
import sys
import json
import time
import shutil
import threading
import subprocess
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _base_dir()
CONFIG_FILE = BASE_DIR / "config" / "channels.json"
API_KEYS_FILE = BASE_DIR / "config" / "api_keys.json"
SERVER_JS_PATH = BASE_DIR / "bridges" / "whatsapp_server" / "server.js"
AUTH_DIR = BASE_DIR / "memory" / "whatsapp_auth"
CONTACTS_FILE = BASE_DIR / "memory" / "whatsapp_contacts.json"
MESSAGES_FILE = BASE_DIR / "memory" / "whatsapp_messages.json"

WA_SERVER_PORT = 3456
PYTHON_RECEIVER_PORT = 3457


# ── Contacts Management ──────────────────────────────────────────────────────

def get_whatsapp_contacts() -> Dict[str, Any]:
    """Loads all known WhatsApp contacts."""
    if CONTACTS_FILE.exists():
        try:
            return json.loads(CONTACTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_whatsapp_contact(name: str, number: str, jid: str, last_message: str = ""):
    """Saves or updates a WhatsApp contact with timestamp and last message."""
    contacts = get_whatsapp_contacts()
    clean_num = number.replace("+", "").replace(" ", "").strip()
    clean_name = name.strip() or f"User_{clean_num[-4:]}" if len(clean_num) >= 4 else clean_num

    prev_count = contacts.get(clean_num, {}).get("message_count", 0)
    contacts[clean_num] = {
        "name": clean_name,
        "number": clean_num,
        "jid": jid or f"{clean_num}@s.whatsapp.net",
        "last_seen": int(time.time()),
        "last_message": last_message,
        "message_count": prev_count + 1,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTACTS_FILE.write_text(json.dumps(contacts, indent=2), encoding="utf-8")


def find_whatsapp_contact(query: str) -> Optional[Dict[str, Any]]:
    """Finds a contact by phone number or contact name (case-insensitive fuzzy match)."""
    contacts = get_whatsapp_contacts()
    if not query or not contacts:
        return None

    clean_q = query.lower().replace("+", "").replace(" ", "").strip()

    # 1. Exact phone number match
    if clean_q in contacts:
        return contacts[clean_q]

    # 2. Number suffix match (e.g. last 10 digits)
    if clean_q.isdigit():
        for num, data in contacts.items():
            if clean_q.endswith(num) or num.endswith(clean_q):
                return data

    # 3. Exact Name match
    for num, data in contacts.items():
        if data.get("name", "").lower().strip() == query.lower().strip():
            return data

    # 4. Partial Name match
    for num, data in contacts.items():
        if query.lower().strip() in data.get("name", "").lower():
            return data

    return None


def list_whatsapp_contacts() -> List[Dict[str, Any]]:
    """Returns a sorted list of all WhatsApp contacts."""
    contacts = get_whatsapp_contacts()
    return sorted(contacts.values(), key=lambda x: x.get("last_seen", 0), reverse=True)


# ── Message History Management ───────────────────────────────────────────────

def get_all_stored_messages() -> List[Dict[str, Any]]:
    """Loads stored message history."""
    if MESSAGES_FILE.exists():
        try:
            return json.loads(MESSAGES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_stored_message(payload: Dict[str, Any]):
    """Stores incoming or outgoing message to persistent history."""
    messages = get_all_stored_messages()
    msg_id = payload.get("id") or f"msg_{int(time.time() * 1000)}"

    # Avoid duplicate saves in message history
    if any(m.get("id") == msg_id for m in messages[-100:]):
        return

    entry = {
        "id": msg_id,
        "from": payload.get("from", ""),
        "sender_number": payload.get("sender_number", ""),
        "name": payload.get("name", "Unknown"),
        "body": payload.get("body", "").strip(),
        "timestamp": payload.get("timestamp", int(time.time())),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "is_group": payload.get("is_group", False),
        "is_from_me": payload.get("is_from_me", False),
        "read": payload.get("read", False),
    }

    messages.append(entry)
    # Keep last 1500 messages
    if len(messages) > 1500:
        messages = messages[-1500:]

    MESSAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    MESSAGES_FILE.write_text(json.dumps(messages, indent=2), encoding="utf-8")


def get_recent_whatsapp_messages(contact_query: Optional[str] = None, limit: int = 10, unread_only: bool = False) -> List[Dict[str, Any]]:
    """Retrieves recent messages filtered by contact and read status."""
    messages = get_all_stored_messages()
    if not messages:
        return []

    target_num = ""
    if contact_query:
        contact = find_whatsapp_contact(contact_query)
        if contact:
            target_num = contact.get("number", "")
        else:
            target_num = contact_query.replace("+", "").replace(" ", "").strip()

    filtered = []
    for m in reversed(messages):
        if unread_only and m.get("read", False):
            continue
        if target_num:
            m_sender = m.get("sender_number", "")
            m_name = m.get("name", "").lower()
            if target_num not in m_sender and contact_query.lower() not in m_name:
                continue
        filtered.append(m)
        if len(filtered) >= limit:
            break

    return list(reversed(filtered))


def mark_messages_as_read(contact_query: Optional[str] = None) -> int:
    """Marks all or contact-specific messages as read."""
    messages = get_all_stored_messages()
    if not messages:
        return 0

    target_num = ""
    if contact_query:
        contact = find_whatsapp_contact(contact_query)
        target_num = contact.get("number", "") if contact else contact_query

    count = 0
    for m in messages:
        if not m.get("read", False):
            if not target_num or target_num in m.get("sender_number", "") or (contact_query and contact_query.lower() in m.get("name", "").lower()):
                m["read"] = True
                count += 1

    if count > 0:
        MESSAGES_FILE.write_text(json.dumps(messages, indent=2), encoding="utf-8")
    return count


def summarize_recent_whatsapp_messages(contact_query: Optional[str] = None, limit: int = 10) -> str:
    """Generates an executive briefing of recent messages using Gemini/LLM."""
    msgs = get_recent_whatsapp_messages(contact_query=contact_query, limit=limit)
    if not msgs:
        return "Boss, WhatsApp par abhi koi recent message nahi hai."

    msg_lines = []
    for m in msgs:
        read_tag = "[Unread]" if not m.get("read") else "[Read]"
        msg_lines.append(f"{m.get('time_str')} | {m.get('name')} (+{m.get('sender_number')}): {m.get('body')} {read_tag}")

    context_str = "\n".join(msg_lines)

    # Use Gemini to summarize
    try:
        if API_KEYS_FILE.exists():
            with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
                key = json.load(f).get("gemini_api_key")
            if key:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=key)
                prompt = (
                    f"Summarize these recent WhatsApp messages for Boss (Saksham) in 2-3 crisp bullet points in Hinglish. "
                    f"Highlight who messaged and what important information they asked or shared:\n\n{context_str}"
                )
                resp = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction="You are MJ, Saksham's executive AI assistant summarizing WhatsApp messages.",
                        temperature=0.4
                    )
                )
                if resp and resp.text:
                    return resp.text.strip()
    except Exception:
        pass

    # Simple text summary fallback
    summary = [f"📬 Recent WhatsApp Messages ({len(msgs)}):"]
    for m in msgs:
        summary.append(f"• *{m.get('name')}* (+{m.get('sender_number')}): \"{m.get('body')}\" ({m.get('time_str')[-8:]})")
    return "\n".join(summary)


# ── Webhook Receiver ─────────────────────────────────────────────────────────

class WhatsAppIncomingHandler(BaseHTTPRequestHandler):
    """Handles incoming webhook POST requests from the Node.js WhatsApp gateway."""

    bridge_instance: Optional['WhatsAppBridge'] = None

    def do_POST(self):
        if self.path == "/wa_incoming":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode("utf-8"))
                if self.bridge_instance:
                    threading.Thread(
                        target=self.bridge_instance.handle_incoming_message,
                        args=(payload,),
                        daemon=True
                    ).start()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class WhatsAppBridge:
    def __init__(self, on_log: Optional[Callable[[str], None]] = None, brain_callback: Optional[Callable[[str, str], str]] = None):
        self.on_log = on_log or (lambda msg: print(f"[WA-BRIDGE] {msg}"))
        self.brain_callback = brain_callback or self._default_ai_reply
        self._server_proc: Optional[subprocess.Popen] = None
        self._http_server: Optional[HTTPServer] = None
        self._running = False
        self._lock = threading.Lock()
        self._processed_msg_ids = set()

    def _read_config(self) -> Dict[str, Any]:
        try:
            if CONFIG_FILE.exists():
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _get_boss_name(self) -> str:
        try:
            if API_KEYS_FILE.exists():
                data = json.loads(API_KEYS_FILE.read_text(encoding="utf-8"))
                name = (data.get("user_name") or "").strip()
                if name and name.lower() != "boss":
                    return name
        except Exception:
            pass
        return "Saksham"

    def _default_ai_reply(self, prompt: str, sender_name: str = "User") -> str:
        """
        Generates AI response using custom persona for WhatsApp:
        Identifies as Saksham's assistant MJ and informs the sender.
        """
        boss_name = self._get_boss_name()
        lower_prompt = prompt.lower().strip()

        # Greetings & Initial message triggers
        greetings = ("hi", "hello", "hey", "namaste", "hlo", "hii", "helo", "hy", "sun", "suno", "yo", "kaise ho", "kya haal")
        is_greeting = any(lower_prompt == g or lower_prompt.startswith(f"{g} ") or lower_prompt.startswith(f"{g},") for g in greetings)

        if is_greeting and len(lower_prompt.split()) <= 4:
            return (
                f"Hi *{sender_name}*! Mai MJ hoon, {boss_name} boss ki assistant. ✨\n\n"
                f"Mai unko bata deti hoon ki aapne message kiya hai! Agar aur kuch jaan-na ya message chhodna ho toh please bataiye."
            )

        # For specific queries or extended conversation, generate intelligent assistant reply
        system_prompt = (
            f"You are MJ, the official personal AI assistant of {boss_name} (your boss). "
            f"You are speaking to '{sender_name}' who just messaged on WhatsApp. "
            f"Always maintain your identity: you are MJ, {boss_name}'s assistant. "
            f"Be polite, witty, and concise. Let them know you have recorded their message for {boss_name}, "
            f"and answer any questions they have. Use WhatsApp formatting (*bold*, _italic_, bullet points)."
        )

        # 1. Try Gemini 3.6 Flash via google-genai SDK
        try:
            with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
                key = json.load(f).get("gemini_api_key")
            if key:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=key)
                resp = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.7,
                    )
                )
                if resp and resp.text:
                    return resp.text.strip()
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                self.on_log("⚠️ Gemini quota rate limit (429) hit. Falling back.")
            else:
                self.on_log(f"Gemini generation error: {e}")

        # 2. Try local LLM / Ollama via call_llm_text
        try:
            from core.llm_client import call_llm_text
            reply = call_llm_text(prompt=prompt, system_prompt=system_prompt)
            if reply and reply.strip():
                return reply.strip()
        except Exception as ex:
            self.on_log(f"Local LLM fallback: {ex}")

        # Fallback template
        return (
            f"Hi *{sender_name}*! Mai MJ hoon, {boss_name} boss ki assistant. "
            f"Maine aapka message note kar liya hai aur mai {boss_name} boss ko inform kar dungi! 👍"
        )

    def start(self) -> bool:
        """Starts both the Python HTTP receiver and the Node.js Baileys gateway."""
        with self._lock:
            if self._running:
                return True

            cfg = self._read_config()
            wa_cfg = cfg.get("whatsapp", {})
            if not wa_cfg.get("enabled", True):
                self.on_log("WhatsApp integration is disabled in config/channels.json")
                return False

            self._running = True

            # 1. Start Python Webhook Receiver
            try:
                WhatsAppIncomingHandler.bridge_instance = self
                self._http_server = HTTPServer(("127.0.0.1", PYTHON_RECEIVER_PORT), WhatsAppIncomingHandler)
                t_receiver = threading.Thread(target=self._http_server.serve_forever, daemon=True)
                t_receiver.start()
                self.on_log(f"WhatsApp receiver listening on 127.0.0.1:{PYTHON_RECEIVER_PORT}")
            except Exception as e:
                self.on_log(f"Receiver port {PYTHON_RECEIVER_PORT} note: {e}")

            # 2. Start Node.js Baileys Gateway Server
            node_bin = shutil.which("node")
            if not node_bin:
                self.on_log("❌ Node.js not found in PATH! WhatsApp gateway cannot start.")
                return False

            env = os.environ.copy()
            env["WA_PORT"] = str(WA_SERVER_PORT)
            env["PYTHON_WEBHOOK_URL"] = f"http://127.0.0.1:{PYTHON_RECEIVER_PORT}/wa_incoming"
            env["WA_AUTH_DIR"] = str(AUTH_DIR)

            try:
                self._server_proc = subprocess.Popen(
                    [node_bin, str(SERVER_JS_PATH)],
                    cwd=str(SERVER_JS_PATH.parent),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                threading.Thread(target=self._pipe_server_logs, daemon=True).start()
                self.on_log("WhatsApp Gateway process started.")
                return True
            except Exception as e:
                self.on_log(f"Failed to launch WhatsApp Gateway: {e}")
                return False

    def _pipe_server_logs(self):
        """Reads stdout from the Node.js server and pipes it to MJ's logger."""
        if not self._server_proc or not self._server_proc.stdout:
            return
        for line in iter(self._server_proc.stdout.readline, ""):
            line_str = line.strip()
            if line_str:
                self.on_log(line_str)

    def stop(self):
        """Stops the gateway server and webhook receiver."""
        with self._lock:
            self._running = False
            if self._server_proc:
                try:
                    self._server_proc.terminate()
                    self._server_proc.wait(timeout=3)
                except Exception:
                    self._server_proc.kill()
                self._server_proc = None

            if self._http_server:
                try:
                    self._http_server.shutdown()
                except Exception:
                    pass
                self._http_server = None
            self.on_log("WhatsApp Bridge stopped.")

    def handle_incoming_message(self, payload: Dict[str, Any]):
        """Processes an incoming WhatsApp message through security filters and MJ's brain."""
        msg_id = payload.get("id", "")
        if msg_id:
            if msg_id in self._processed_msg_ids:
                return
            self._processed_msg_ids.add(msg_id)
            if len(self._processed_msg_ids) > 5000:
                try:
                    self._processed_msg_ids.pop()
                except KeyError:
                    pass

        sender_num = payload.get("sender_number", "")
        sender_name = payload.get("name", "Unknown")
        body = payload.get("body", "").strip()
        is_group = payload.get("is_group", False)
        from_jid = payload.get("from", "")

        # 1. Save Contact in WhatsApp Contacts memory
        save_whatsapp_contact(
            name=sender_name,
            number=sender_num,
            jid=from_jid,
            last_message=body
        )

        # 2. Save Message to persistent Message History
        save_stored_message(payload)

        cfg = self._read_config()
        whitelist = cfg.get("whitelist", {})
        allowed_nums = [n.replace("+", "").replace(" ", "").strip() for n in whitelist.get("allowed_whatsapp_numbers", [])]
        respond_to_all = whitelist.get("respond_to_all", True)
        prefix = whitelist.get("prefix", "!mj").lower().strip()
        require_prefix = whitelist.get("require_prefix", False)

        # Whitelist Check
        if not respond_to_all and allowed_nums:
            clean_sender = sender_num.replace("+", "").strip()
            if clean_sender not in allowed_nums:
                self.on_log(f"Ignored message from unauthorized sender: {sender_num}")
                return

        # Prefix Check (for groups)
        query = body
        if is_group or require_prefix:
            if not body.lower().startswith(prefix):
                return
            query = body[len(prefix):].strip()

        if not query:
            return

        self.on_log(f"💬 [WHATSAPP MSG] From: {sender_name} (+{sender_num}) -> '{query}'")

        # Generate custom assistant response
        try:
            if callable(self.brain_callback):
                try:
                    ai_reply = self.brain_callback(query, sender_name)
                except TypeError:
                    ai_reply = self.brain_callback(query)
            else:
                ai_reply = self._default_ai_reply(query, sender_name)

            if ai_reply:
                self.send_message(to=from_jid or sender_num, text=ai_reply)
                self.on_log(f"🤖 [MJ -> {sender_name}]: {ai_reply[:80]}...")
        except Exception as e:
            self.on_log(f"Error generating AI reply: {e}")

    def send_message(self, to: str, text: str) -> bool:
        """Sends a WhatsApp message via the local gateway HTTP API."""
        try:
            req_data = json.dumps({"to": to, "text": text}).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{WA_SERVER_PORT}/send",
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                success = result.get("success", False)
                if success:
                    # Record outgoing message in history
                    save_stored_message({
                        "id": f"out_{int(time.time()*1000)}",
                        "from": to,
                        "sender_number": to.replace("@s.whatsapp.net", ""),
                        "name": "MJ (Assistant)",
                        "body": text,
                        "timestamp": int(time.time()),
                        "is_group": False,
                        "is_from_me": True,
                        "read": True,
                    })
                return success
        except Exception as e:
            self.on_log(f"Failed to send WhatsApp message to {to}: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Queries gateway server status and QR code availability."""
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{WA_SERVER_PORT}/status", timeout=2) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return {"status": "offline", "is_connected": False, "qr": None}


_global_bridge: Optional[WhatsAppBridge] = None

def get_whatsapp_bridge(on_log=None, brain_callback=None) -> WhatsAppBridge:
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = WhatsAppBridge(on_log=on_log, brain_callback=brain_callback)
    return _global_bridge
