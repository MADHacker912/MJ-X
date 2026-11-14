"""Voice and response-style profiles with artifact-free PCM16 processing."""

from __future__ import annotations

from typing import Any
from mjx.emotions.voice_expression import ACOUSTIC_PROFILES, VoiceAcoustics, VoiceExpressionController

_VOICE = {
    emo: (p.style, p.speed, p.volume, p.pitch)
    for emo, p in ACOUSTIC_PROFILES.items()
}

_TYPING = {
    "excited": "fast", "happy": "fast", "laughing": "fast",
    "sad": "slow", "crying": "slow", "sleepy": "slow",
    "thinking": "slow", "serious": "medium", "worried": "medium",
}

_controller = VoiceExpressionController()


def get_voice_settings(emotion: str, intensity: float = 0.5) -> dict[str, Any]:
    acoustics = _controller.compute_acoustics(emotion, intensity)
    return {
        "voice_style": acoustics.style,
        "speed": acoustics.speed,
        "volume": acoustics.volume,
        "pitch": acoustics.pitch,
        "pause_ms": acoustics.pause_ms,
        "typing_speed": _TYPING.get(emotion, "medium"),
    }


def apply_pcm16_settings(data: bytes, settings: dict[str, Any]) -> bytes:
    """Apply clean volume leveling and smooth soft-knee limiting to 24 kHz mono PCM without artifacts."""
    if not settings.get("voice_emotions_enabled", True):
        return data

    try:
        vol = float(settings.get("volume", settings.get("voice_volume", 1.0)))
        acoustics = VoiceAcoustics(
            style=str(settings.get("voice_style", "balanced")),
            speed=float(settings.get("speed", 1.0)),
            volume=vol,
            pitch=float(settings.get("pitch", 1.0)),
            pause_ms=int(settings.get("pause_ms", 300)),
        )
        return _controller.process_pcm16_chunk(data, acoustics)
    except Exception:
        return data
