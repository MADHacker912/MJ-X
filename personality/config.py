"""Validated personality configuration with user-config overrides."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any

from memory.config_manager import load_api_keys


CONFIG_PATH = Path(__file__).with_name("personality.config.json")
DEFAULTS: dict[str, Any] = {
    "friend_mode_enabled": True,
    "default_language": "hinglish",
    "honesty_level": 1.0,
    "directness": 0.85,
    "humour_level": 0.45,
    "emoji_frequency": 0.2,
    "challenge_assumptions": True,
    "fake_praise_blocked": True,
    "emotion_engine_enabled": True,
    "avatar_expression_enabled": True,
    "voice_emotion_enabled": True,
    "memory_personalisation_enabled": True,
    "maximum_slang_level": 0.55,
    "serious_mode_auto_detection": True,
}


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "off", "no", "0", ""}
    return bool(value)


def validate_settings(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = raw or {}
    result = {**DEFAULTS, **{key: raw[key] for key in DEFAULTS if key in raw}}
    for key, default in DEFAULTS.items():
        if isinstance(default, bool):
            result[key] = _bool(result[key])
        elif isinstance(default, float):
            try:
                result[key] = round(max(0.0, min(1.0, float(result[key]))), 3)
            except (TypeError, ValueError):
                result[key] = default
    language = str(result["default_language"]).strip().lower()
    result["default_language"] = language if language in {"hinglish", "hindi", "english", "auto"} else "hinglish"
    return result


def load_settings() -> dict[str, Any]:
    raw: dict[str, Any] = {}
    try:
        raw.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        pass
    raw.update({key: value for key, value in load_api_keys().items() if key in DEFAULTS})
    return validate_settings(raw)


def save_settings(**changes: Any) -> dict[str, Any]:
    unknown = set(changes) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"Unknown personality settings: {', '.join(sorted(unknown))}")
    settings = validate_settings({**load_settings(), **changes})
    fd, temp_name = tempfile.mkstemp(prefix=".personality.", suffix=".tmp", dir=CONFIG_PATH.parent)
    try:
        with open(fd, "w", encoding="utf-8", closefd=True) as handle:
            json.dump(settings, handle, indent=2)
            handle.flush()
        Path(temp_name).replace(CONFIG_PATH)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return settings
