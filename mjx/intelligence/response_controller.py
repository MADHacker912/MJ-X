"""
mjx.intelligence.response_controller — Output Formatting & Uncertainty Communication.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ResponseFormatConfig:
    preferred_length: str = "concise"  # "concise", "detailed", "bullet_points"
    language_mode: str = "hinglish"    # "english", "hindi", "hinglish"
    tone: str = "friendly_direct"
    confidence_threshold: float = 0.65


class ResponseController:
    """Formats assistant output with tone calibration and confidence estimation."""

    def __init__(self, config: Optional[ResponseFormatConfig] = None):
        self.config = config or ResponseFormatConfig()

    def format_response(
        self,
        raw_text: str,
        confidence: float = 1.0,
        is_hinglish: Optional[bool] = None,
        tone: Optional[str] = None,
    ) -> str:
        text = raw_text.strip()
        active_tone = tone or self.config.tone

        # Uncertainty preface if confidence is below threshold
        if confidence < self.config.confidence_threshold:
            use_hinglish = is_hinglish if is_hinglish is not None else (self.config.language_mode == "hinglish")
            if use_hinglish:
                prefix = "Main is baat par poori tarah sure nahi hu, lekin jahan tak mujhe pata hai: "
            else:
                prefix = "I'm not completely certain about this, but to the best of my knowledge: "
            text = f"{prefix}{text}"

        return text
