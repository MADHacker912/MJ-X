#!/usr/bin/env python3
"""
scripts/link_whatsapp.py — QR Code Scanner & WhatsApp Linker for MJ.
====================================================================
Run this script in your terminal to display the WhatsApp QR code,
scan it with your phone (WhatsApp -> Linked Devices -> Link a Device),
and link MJ directly to your WhatsApp.
"""

import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from bridges.whatsapp_bridge import get_whatsapp_bridge

def main():
    print("\n" + "=" * 60)
    print("  📲 MJ WHATSAPP LINKING UTILITY")
    print("=" * 60)
    print("\n[1] Starting WhatsApp Baileys Multi-Device Gateway...")

    bridge = get_whatsapp_bridge(on_log=lambda msg: print(msg))
    if not bridge.start():
        print("❌ Failed to start WhatsApp Gateway. Ensure Node.js is installed.")
        return

    print("\n[2] Waiting for QR code generation...")
    print("    Open WhatsApp on your phone -> Settings -> Linked Devices -> Link a Device.\n")

    try:
        while True:
            time.sleep(2)
            stat = bridge.get_status()
            if stat.get("is_connected", False):
                print("\n" + "=" * 60)
                print(f"  🎉 SUCCESS! WhatsApp is CONNECTED as: {stat.get('user_jid')}")
                print("  MJ can now receive and reply to WhatsApp messages!")
                print("=" * 60 + "\n")
                break
    except KeyboardInterrupt:
        print("\nStopping WhatsApp linker...")
    finally:
        # Keep background server running or stop
        pass

if __name__ == "__main__":
    main()
