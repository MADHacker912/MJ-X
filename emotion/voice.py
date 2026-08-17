"""Voice and response-style profiles for simulated emotions."""

from __future__ import annotations

from typing import Any


_VOICE = {
    "neutral": ("balanced", 1.0, 1.0, 1.0),
    "happy": ("cheerful", 1.07, 1.04, 1.02),
    "excited": ("energetic", 1.12, 1.08, 1.04),
    "laughing": ("playful", 1.08, 1.06, 1.02),
    "sad": ("soft", 0.91, 0.86, 0.98),
    "crying": ("calm_supportive", 0.88, 0.82, 0.97),
    "confused": ("questioning", 0.96, 0.98, 1.01),
    "surprised": ("bright_surprised", 1.08, 1.04, 1.03),
    "worried": ("concerned", 0.94, 0.92, 0.99),
    "angry": ("firm_controlled", 0.98, 1.04, 0.98),
    "annoyed": ("restrained", 0.98, 0.98, 0.99),
    "embarrassed": ("gentle", 0.96, 0.94, 1.01),
    "shy": ("quiet_gentle", 0.93, 0.87, 1.01),
    "proud": ("warm_confident", 1.03, 1.02, 1.01),
    "curious": ("engaged_questioning", 1.02, 1.0, 1.02),
    "caring": ("warm_supportive", 0.94, 0.9, 1.0),
    "serious": ("steady_clear", 0.96, 1.0, 0.99),
    "sleepy": ("slow_relaxed", 0.86, 0.82, 0.98),
    "thinking": ("reflective", 0.92, 0.94, 0.99),
    "scared": ("controlled_cautious", 0.96, 0.92, 1.02),
    "disappointed": ("subdued", 0.91, 0.88, 0.98),
}

_TYPING = {
    "excited": "fast", "happy": "fast", "laughing": "fast",
    "sad": "slow", "crying": "slow", "sleepy": "slow",
    "thinking": "slow", "serious": "medium", "worried": "medium",
}


def get_voice_settings(emotion: str, intensity: float = 0.5) -> dict:
    style, speed, volume, pitch = _VOICE.get(emotion, _VOICE["neutral"])
    amount = max(0.0, min(1.0, intensity))
    return {
        "voice_style": style,
        "speed": round(1.0 + (speed - 1.0) * amount, 3),
        "volume": round(1.0 + (volume - 1.0) * amount, 3),
        "pitch": round(1.0 + (pitch - 1.0) * amount, 3),
        "typing_speed": _TYPING.get(emotion, "medium"),
    }


def apply_pcm16_settings(data: bytes, settings: dict[str, Any]) -> bytes:
    """Apply clean volume leveling and smooth audio scaling to 24 kHz mono PCM without artifacts."""
    try:
        import numpy as np

        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        if samples.size < 2:
            return data
        volume = max(0.8, min(1.25, float(settings.get("volume", 1.0))))
        if volume != 1.0:
            samples *= volume
        return np.clip(samples, -32768, 32767).astype(np.int16).tobytes()
    except Exception:
        return data
