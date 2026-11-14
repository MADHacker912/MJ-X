# MJ-X SINGULARITY — 15 DEPLOYMENT GUIDE

**Target Environments:** Linux (Ubuntu 22.04+ / Debian 12+), Windows 10/11  
**Prerequisites:** Python 3.11 - 3.14, PortAudio, ALSA/PulseAudio, SQLite3

---

## 1. SYSTEM DEPENDENCY SETUP (LINUX)

```bash
# Update system packages
sudo apt-get update

# Install audio, GUI and build dependencies
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    python3-venv \
    portaudio19-dev \
    libasound2-dev \
    sqlite3 \
    libgl1-mesa-glx \
    libegl1 \
    libxcb-xinerama0 \
    libxcb-cursor0
```

---

## 2. PYTHON VIRTUAL ENVIRONMENT & PIP INSTALLATION

```bash
cd /home/obito/Documents/MJ-X

# Optional: Initialize fresh virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required Python dependencies
pip install --upgrade pip
pip install \
    PyQt6 \
    google-genai \
    pyaudio \
    numpy \
    cryptography \
    fastapi \
    "uvicorn[standard]" \
    pyautogui \
    pyperclip \
    duckduckgo_search \
    psutil \
    pytest \
    pytest-asyncio
```

---

## 3. CONFIGURATION & CREDENTIAL SETUP

1. **Vault Configuration:**
   Place your Gemini API key in `config/api_keys.json` or register it directly into the OS Vault:
   ```python
   from mjx.security import set_api_key
   set_api_key("gemini_api_key", "AIzaSy...")
   ```
2. **Settings Configuration:**
   Inspect or customize `memory/config.json`:
   ```json
   {
       "brief_mode": false,
       "voice_interruption_enabled": true,
       "emotion_engine_enabled": true,
       "selected_voice": "Aoede"
   }
   ```
3. **Database Directory:**
   Ensure directory `data/` exists and is writable:
   ```bash
   mkdir -p data
   ```

---

## 4. LAUNCHING THE APPLICATION

```bash
# Run the application in desktop GUI mode
cd /home/obito/Documents/MJ-X
PYTHONPATH=. python3 main.py
```

### Systemd Service Configuration (Optional Background Auto-start)
```ini
[Unit]
Description=MJ-X Desktop AI Ecosystem
After=network.target sound.target

[Service]
Type=simple
User=obito
WorkingDirectory=/home/obito/Documents/MJ-X
Environment=PYTHONPATH=/home/obito/Documents/MJ-X
Environment=DISPLAY=:0
ExecStart=/usr/bin/python3 /home/obito/Documents/MJ-X/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```
