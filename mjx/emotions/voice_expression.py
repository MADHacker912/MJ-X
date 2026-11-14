"""
mjx.emotions.voice_expression — Acoustic Parameter Mapping, Soft-Knee Limiting, and Audio Prosody.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class VoiceAcoustics:
    style: str
    speed: float       # Speed multiplier (e.g. 0.85 to 1.15)
    volume: float      # Volume multiplier (e.g. 0.8 to 1.25)
    pitch: float       # Pitch multiplier (e.g. 0.85 to 1.15)
    pause_ms: int      # Inter-sentence pause in milliseconds


ACOUSTIC_PROFILES = {
    "neutral": VoiceAcoustics("balanced", 1.0, 1.0, 1.0, 300),
    "happy": VoiceAcoustics("cheerful", 1.07, 1.04, 1.02, 220),
    "excited": VoiceAcoustics("energetic", 1.12, 1.06, 1.04, 180),
    "laughing": VoiceAcoustics("playful", 1.08, 1.05, 1.02, 200),
    "sad": VoiceAcoustics("soft", 0.91, 0.88, 0.98, 450),
    "crying": VoiceAcoustics("supportive", 0.88, 0.84, 0.97, 500),
    "confused": VoiceAcoustics("questioning", 0.96, 0.98, 1.01, 350),
    "surprised": VoiceAcoustics("bright_surprised", 1.06, 1.04, 1.03, 240),
    "worried": VoiceAcoustics("concerned", 0.94, 0.92, 0.99, 400),
    "angry": VoiceAcoustics("firm_controlled", 0.98, 1.04, 0.98, 300),
    "annoyed": VoiceAcoustics("restrained", 1.02, 0.98, 0.99, 250),
    "embarrassed": VoiceAcoustics("gentle", 0.96, 0.94, 1.01, 360),
    "shy": VoiceAcoustics("quiet_gentle", 0.93, 0.88, 1.01, 400),
    "proud": VoiceAcoustics("warm_confident", 1.03, 1.02, 1.01, 260),
    "curious": VoiceAcoustics("engaged_questioning", 1.02, 1.0, 1.02, 280),
    "caring": VoiceAcoustics("warm_supportive", 0.94, 0.92, 1.0, 380),
    "serious": VoiceAcoustics("steady_clear", 0.96, 1.0, 0.99, 380),
    "sleepy": VoiceAcoustics("slow_relaxed", 0.86, 0.84, 0.98, 550),
    "thinking": VoiceAcoustics("reflective", 0.92, 0.94, 0.99, 420),
    "scared": VoiceAcoustics("controlled_cautious", 0.96, 0.92, 1.02, 350),
    "disappointed": VoiceAcoustics("subdued", 0.91, 0.88, 0.98, 450),
}


class VoiceExpressionController:
    """Computes acoustic modulation targets according to emotion and intensity with soft-knee limiting."""

    def compute_acoustics(self, emotion: str, intensity: float = 0.5) -> VoiceAcoustics:
        base = ACOUSTIC_PROFILES.get(emotion, ACOUSTIC_PROFILES["neutral"])
        amt = max(0.0, min(1.0, intensity))

        return VoiceAcoustics(
            style=base.style,
            speed=round(1.0 + (base.speed - 1.0) * amt, 3),
            volume=round(1.0 + (base.volume - 1.0) * amt, 3),
            pitch=round(1.0 + (base.pitch - 1.0) * amt, 3),
            pause_ms=int(300 + (base.pause_ms - 300) * amt),
        )

    def process_pcm16_chunk(self, data: bytes, acoustics: VoiceAcoustics) -> bytes:
        """
        Applies clean gain modulation and soft-knee limiting to 24 kHz mono 16-bit PCM.
        Eliminates digital clipping, harsh pops, and audible distortion.
        """
        if not data or len(data) < 2:
            return data

        try:
            import numpy as np
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            vol = max(0.8, min(1.25, float(acoustics.volume)))
            if vol != 1.0:
                samples *= vol

            # Soft-knee limiting: smooth hyperbolic tangent curve above 28000
            over = np.abs(samples) > 28000.0
            if np.any(over):
                sign = np.sign(samples)
                excess = (np.abs(samples) - 28000.0) / 4768.0
                compressed = 28000.0 + 4767.0 * np.tanh(excess)
                samples = np.where(over, sign * compressed, samples)

            return np.clip(samples, -32768, 32767).astype(np.int16).tobytes()
        except ImportError:
            return data
