"""Response, avatar, gesture, and voice mapping for conversation modes."""

from __future__ import annotations

import zlib
from typing import Any


_STYLE = {
    "casual_friend": ("relaxed_natural", "Brief, natural Hinglish; light wit only when it fits."),
    "honest_advisor": ("direct_analytical", "Answer first, then practical trade-offs, risks, and a recommendation."),
    "teacher": ("simple_patient", "Explain one step at a time with a concrete example; never patronise."),
    "supportive": ("calm_supportive", "Acknowledge the feeling briefly, avoid a lecture, then give one practical next step."),
    "serious": ("calm_direct", "No jokes. State the warning clearly and give the safest useful alternative."),
    "debate": ("respectful_challenger", "Separate facts from opinions, test assumptions, and change position when evidence wins."),
}

_MODE_GESTURES = {
    "casual_friend": ("small_nod", "subtle_shrug", "none"),
    "honest_advisor": ("small_nod", "open_palm"),
    "teacher": ("explain_step", "small_nod"),
    "supportive": ("gentle_nod", "none"),
    "serious": ("steady", "small_nod"),
    "debate": ("open_palm", "thinking_pause"),
}

_EXPRESSIONS = {
    "casual_friend": "neutral_warm", "honest_advisor": "serious_soft",
    "teacher": "focused_curious", "supportive": "caring_soft",
    "serious": "serious_soft", "debate": "focused_curious",
}


class ResponseStyleManager:
    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings

    def get(self, mode: str, preferences: dict[str, Any]) -> dict[str, Any]:
        name, base_guidance = _STYLE.get(mode, _STYLE["casual_friend"])
        guidance = self._build_guidance(base_guidance, preferences)
        return {
            "name": name,
            "guidance": guidance,
            "language": preferences.get("preferred_language", self.settings["default_language"]),
            "directness": self._map_directness(preferences.get("directness", self.settings["directness"])),
            "honesty": self._map_honesty(preferences.get("honesty_level", self.settings["honesty_level"])),
            "humour": 0.0 if mode in {"serious", "supportive"} else self._map_humour(preferences.get("humour_level", self.settings["humour_level"])),
            "emoji_frequency": preferences.get("emoji_frequency", self.settings["emoji_frequency"]),
            "maximum_slang": self.settings["maximum_slang_level"],
        }

    @staticmethod
    def _map_directness(value: Any) -> float:
        if isinstance(value, str):
            low = value.casefold()
            if "gentle" in low or "soft" in low:
                return 0.45
            if "direct" in low or "blunt" in low or "high" in low:
                return 0.95
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 0.85

    @staticmethod
    def _map_honesty(value: Any) -> float:
        if isinstance(value, str):
            low = value.casefold()
            if "low" in low:
                return 0.45
            if "medium" in low:
                return 0.75
            if "high" in low or "honest" in low:
                return 1.0
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 1.0

    @staticmethod
    def _map_humour(value: Any) -> float:
        if isinstance(value, str):
            low = value.casefold()
            if any(token in low for token in ("none", "no", "zero", "avoid")):
                return 0.0
            if "low" in low:
                return 0.15
            if "medium" in low or "normal" in low:
                return 0.45
            if "high" in low or "funny" in low:
                return 0.75
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 0.45

    def _build_guidance(self, base_guidance: str, preferences: dict[str, Any]) -> str:
        response_length = str(preferences.get("response_length", "normal") or "normal").lower()
        avoid_repetition = bool(preferences.get("avoid_repetition", False))
        guidance = base_guidance
        if response_length == "brief":
            guidance = f"{guidance} Keep the answer concise and to the point."
        elif response_length == "detailed":
            guidance = f"{guidance} Provide a complete explanation with examples and concrete steps when helpful."
        if avoid_repetition:
            guidance = f"{guidance} Do not repeat the same content twice or restate the answer redundantly."
        return guidance

    def avatar(self, mode: str, emotion: str, seed: str = "") -> dict[str, Any]:
        gestures = _MODE_GESTURES.get(mode, ("none",))
        index = zlib.crc32(seed.encode("utf-8", errors="ignore")) % len(gestures)
        expression = _EXPRESSIONS.get(mode, "neutral_warm")
        if emotion in {"confused", "worried", "annoyed", "surprised", "laughing", "happy"}:
            expression = f"{emotion}_soft" if emotion not in {"laughing", "happy"} else emotion
        return {
            "state": "thinking",
            "expression": expression,
            "gesture": gestures[index],
            "eye_contact": mode not in {"thinking"},
        }

    @staticmethod
    def voice(mode: str) -> dict[str, Any]:
        return {
            "style": {
                "casual_friend": "warm_natural", "honest_advisor": "calm_direct",
                "teacher": "clear_patient", "supportive": "warm_supportive",
                "serious": "steady_clear", "debate": "confident_measured",
            }.get(mode, "balanced"),
            "speed": 0.94 if mode in {"supportive", "serious"} else 1.0,
            "pitch": 1.0,
        }


class HumourController:
    @staticmethod
    def guidance(mode: str, level: float) -> str:
        if mode in {"serious", "supportive"}:
            return "Do not use humour in this response."
        if level < 0.2:
            return "Avoid jokes."
        return "At most one light, context-appropriate witty line; never force slang or humour."
