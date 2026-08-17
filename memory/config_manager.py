import json
import sys
import tempfile
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

EMOTION_DEFAULTS = {
    "emotion_engine_enabled": True,
    "avatar_emotions_enabled": True,
    "voice_emotions_enabled": True,
    "emotion_intensity": 0.8,
    "emoji_frequency": "low",
    "emotion_decay_time": 180,
    "allow_emotion_memory": True,
}

def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

def save_api_keys(gemini_api_key: str) -> None:
    ensure_config_dir()

    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["gemini_api_key"] = gemini_api_key.strip()

    CONFIG_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

def load_api_keys() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}

def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")

def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

def save_api_keys(gemini_api_key: str) -> None:
    ensure_config_dir()

    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["gemini_api_key"] = gemini_api_key.strip()

    CONFIG_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

def load_api_keys() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}

def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")

def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)


def get_assistant_name() -> str:
    """Return the configured assistant name, or 'MJ' if not set."""
    return load_api_keys().get("assistant_name", "MJ") or "MJ"


def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")


def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["assistant_name"] = assistant_name.strip() or "MJ"
    data["user_name"] = user_name.strip()
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


def get_voice_interruption_enabled() -> bool:
    """Return whether speech may automatically interrupt MJ's voice."""
    value = load_api_keys().get("voice_interruption_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    return bool(value)


def save_voice_interruption_enabled(enabled: bool) -> None:
    """Persist automatic voice interruption without changing other settings."""
    ensure_config_dir()
    data = load_api_keys()
    data["voice_interruption_enabled"] = bool(enabled)
    fd, temp_name = tempfile.mkstemp(prefix=".api_keys.", suffix=".tmp", dir=CONFIG_DIR)
    try:
        with open(fd, "w", encoding="utf-8", closefd=True) as handle:
            json.dump(data, handle, indent=4)
            handle.flush()
        Path(temp_name).replace(CONFIG_FILE)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def save_brief_enabled(enabled: bool) -> None:
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["morning_brief_enabled"] = enabled
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_emotion_settings() -> dict:
    """Return validated developer settings with backwards-compatible defaults."""
    return _validate_emotion_settings(load_api_keys())


def _validate_emotion_settings(raw: dict) -> dict:
    settings = {key: raw.get(key, value) for key, value in EMOTION_DEFAULTS.items()}

    def as_bool(value) -> bool:
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off", ""}
        return bool(value)

    for key in ("emotion_engine_enabled", "avatar_emotions_enabled", "voice_emotions_enabled", "allow_emotion_memory"):
        settings[key] = as_bool(settings[key])
    try:
        settings["emotion_intensity"] = max(0.0, min(1.0, float(settings["emotion_intensity"])))
    except (TypeError, ValueError):
        settings["emotion_intensity"] = EMOTION_DEFAULTS["emotion_intensity"]
    try:
        settings["emotion_decay_time"] = max(15, min(3600, int(settings["emotion_decay_time"])))
    except (TypeError, ValueError):
        settings["emotion_decay_time"] = EMOTION_DEFAULTS["emotion_decay_time"]
    emoji = str(settings["emoji_frequency"]).lower()
    settings["emoji_frequency"] = emoji if emoji in {"none", "low", "medium", "high"} else "low"
    return settings


def save_emotion_settings(**changes) -> dict:
    """Validate and atomically persist Emotion Engine developer settings."""
    unknown = set(changes) - set(EMOTION_DEFAULTS)
    if unknown:
        raise ValueError(f"Unknown emotion settings: {', '.join(sorted(unknown))}")
    current = get_emotion_settings()
    current.update(changes)
    current = _validate_emotion_settings(current)
    data = load_api_keys()
    data.update(current)
    ensure_config_dir()
    fd, temp_name = tempfile.mkstemp(prefix=".api_keys.", suffix=".tmp", dir=CONFIG_DIR)
    try:
        with open(fd, "w", encoding="utf-8", closefd=True) as handle:
            json.dump(data, handle, indent=4)
            handle.flush()
        Path(temp_name).replace(CONFIG_FILE)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return get_emotion_settings()
