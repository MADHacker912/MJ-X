# 📱 MJ-X Android Autonomous Agent

MJ-X Android Client acts as the physical hands, eyes, and voice of MJ-X on your Android phone.

## 🔑 Permissions Granted & Capabilities
1. **Accessibility Service (`MJAccessibilityService`)**:
   - Programmatic screen taps, swipes, and clicks without root.
   - Text input into input fields.
   - Global navigation: Back, Home, Recents, Notifications.
   - Reads current on-screen UI hierarchy tree for Gemini AI vision reasoning.
2. **System Alert Window (`SYSTEM_ALERT_WINDOW`)**:
   - Floating Cyberpunk HUD button (⚡) on top of any app.
3. **Audio Record (`RECORD_AUDIO`)**:
   - Voice streaming to MJ-X.
4. **Telephony & Contacts (`CALL_PHONE`, `READ_CONTACTS`, `SEND_SMS`)**:
   - Autonomous calling and messaging.
5. **Package Manager (`QUERY_ALL_PACKAGES`)**:
   - Launching any app on phone (WhatsApp, YouTube, Camera, etc.).

## 🚀 How to Build & Run
1. Open the `android/` folder in **Android Studio**.
2. Connect your Android phone via USB (with USB Debugging ON) or run on emulator.
3. Click **Run** (or `gradle assembleDebug`).
4. On phone:
   - Click **"1. Grant Phone & Overlay Permissions"**.
   - Click **"2. Enable Accessibility"** -> Select **MJ-X Assistant** -> Toggle **ON**.
   - Enter your Laptop's Local IP (`192.168.x.x:8000`).
   - Tap **"START AUTONOMOUS AGENT"**.
