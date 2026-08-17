"""
actions/whatsapp_action.py — WhatsApp Control & Messaging Action for MJ AI.
===========================================================================
Allows MJ to check recent messages, summarize unread chats, send messages by
Contact Name or Number, list contacts, and save new contacts.
"""

import sys
from pathlib import Path
from typing import Dict, Any

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _base_dir()


def whatsapp_action(parameters: dict, player=None, speak=None) -> str:
    """
    Dispatches WhatsApp commands:
    - recent / check: Read recent messages (param: contact='Rahul' or None for all)
    - summary / unread: AI executive brief of recent/unread messages
    - send: Send message by contact name (e.g. 'Rahul') or phone number ('+91...')
    - list_contacts: View all recorded WhatsApp contacts
    - add_contact: Save or nickname a contact (params: name, number)
    - status: Check connection status
    """
    action = str(parameters.get("action", "recent")).lower().strip()
    to = str(parameters.get("to", "") or parameters.get("phone", "") or parameters.get("number", "") or parameters.get("contact", "") or parameters.get("name", "")).strip()
    text = str(parameters.get("text", "") or parameters.get("message", "")).strip()
    limit = int(parameters.get("limit", 10))

    from bridges.whatsapp_bridge import (
        get_whatsapp_bridge,
        find_whatsapp_contact,
        list_whatsapp_contacts,
        save_whatsapp_contact,
        get_recent_whatsapp_messages,
        summarize_recent_whatsapp_messages,
        mark_messages_as_read
    )
    bridge = get_whatsapp_bridge()

    # 1. Check Recent Messages
    if action in ("recent", "check", "read", "read_messages", "messages", "inbox"):
        msgs = get_recent_whatsapp_messages(contact_query=to or None, limit=limit)
        if not msgs:
            target_desc = f"from '{to}'" if to else ""
            res = f"No recent WhatsApp messages found {target_desc}."
            if player and hasattr(player, "show_content"):
                player.show_content("WHATSAPP MESSAGES", res)
            return res

        lines = [f"📬 Recent WhatsApp Messages ({len(msgs)}):"]
        for m in msgs:
            sender_tag = m.get("name", "Unknown")
            num_tag = f"+{m.get('sender_number', '')}"
            body_tag = m.get("body", "")
            time_tag = m.get("time_str", "")[-8:]
            read_status = "✓✓" if m.get("read") else "🔴 UNREAD"
            lines.append(f"• [{time_tag}] {read_status} *{sender_tag}* ({num_tag}):\n  \"{body_tag}\"")

        # Mark them as read
        mark_messages_as_read(to or None)
        res = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("WHATSAPP INBOX", res)
        return res

    # 2. Executive Summary / Unread Messages
    elif action in ("summary", "unread", "brief"):
        res = summarize_recent_whatsapp_messages(contact_query=to or None, limit=limit)
        if player and hasattr(player, "show_content"):
            player.show_content("WHATSAPP BRIEFING", res)
        return res

    # 3. Add / Save Contact
    elif action in ("add_contact", "save_contact", "create_contact"):
        contact_name = str(parameters.get("name", "") or to).strip()
        contact_num = str(parameters.get("number", "") or parameters.get("phone", "")).strip()
        if not contact_name or not contact_num:
            return "Error: Please provide both 'name' and 'number' to save a WhatsApp contact."
        clean_digits = "".join(filter(str.isdigit, contact_num))
        jid = f"{clean_digits}@s.whatsapp.net"
        save_whatsapp_contact(name=contact_name, number=clean_digits, jid=jid, last_message="Manual Entry")
        res = f"✅ Saved contact: *{contact_name}* (+{clean_digits}) to WhatsApp memory."
        if player and hasattr(player, "append_log"):
            player.append_log(f"SYS: {res}")
        return res

    # 4. List Contacts
    elif action in ("list_contacts", "contacts", "get_contacts"):
        contacts = list_whatsapp_contacts()
        if not contacts:
            return "No WhatsApp contacts recorded yet. When someone messages on WhatsApp or you use add_contact, they will appear here."

        lines = [f"📱 Recorded WhatsApp Contacts ({len(contacts)}):"]
        for c in contacts:
            lines.append(f"• *{c.get('name', 'Unknown')}* (+{c.get('number', '')}) — Last seen: {c.get('updated_at', '')} | Msg: \"{c.get('last_message', '')[:35]}\"")
        res = "\n".join(lines)
        if player and hasattr(player, "show_content"):
            player.show_content("WHATSAPP CONTACTS", res)
        return res

    # 5. Send Message
    elif action == "send":
        if not to:
            return "Error: Missing recipient name or phone number ('to')."
        if not text:
            return f"Error: Missing message content ('text') to send to {to}."

        resolved_target = to
        target_name = to
        contact = find_whatsapp_contact(to)

        if contact:
            resolved_target = contact.get("jid") or contact.get("number")
            target_name = contact.get("name", to)
        else:
            clean_digits = "".join(filter(str.isdigit, to))
            if len(clean_digits) < 7:
                known = [c.get("name", "") for c in list_whatsapp_contacts() if c.get("name")]
                known_str = ", ".join(known) if known else "None"
                return f"Could not find contact '{to}' in WhatsApp memory. Known contacts: {known_str}. Please provide their phone number."

        success = bridge.send_message(to=resolved_target, text=text)
        if success:
            res = f"✅ WhatsApp message successfully sent to {target_name} ({resolved_target}): '{text}'"
            if player and hasattr(player, "append_log"):
                player.append_log(f"WA SENT -> {target_name}: {text}")
            return res
        else:
            return f"❌ Failed to send WhatsApp message to {target_name}. Please ensure WhatsApp is connected in Settings."

    # 6. Status
    elif action == "status":
        stat = bridge.get_status()
        is_conn = stat.get("is_connected", False)
        status_str = stat.get("status", "unknown")
        user = stat.get("user_jid", "none")
        contacts_count = len(list_whatsapp_contacts())
        unread_count = len(get_recent_whatsapp_messages(unread_only=True))
        res = f"WhatsApp Status: {status_str.upper()} (Connected: {is_conn}, User: {user}, Contacts: {contacts_count}, Unread Messages: {unread_count})"
        if player and hasattr(player, "show_content"):
            player.show_content("WHATSAPP STATUS", res)
        return res

    elif action == "start":
        started = bridge.start()
        return "WhatsApp bridge started. Scan QR code in settings if not linked." if started else "Failed to start WhatsApp bridge."

    elif action == "stop":
        bridge.stop()
        return "WhatsApp bridge stopped."

    return "Available WhatsApp actions: recent | summary | send | list_contacts | add_contact | status"
