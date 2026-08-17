"""UI-neutral mappings from emotions to avatar expression animations."""

from __future__ import annotations


_AVATAR = {
    "neutral": ("calm_idle", "neutral"),
    "happy": ("smile_bounce", "smiling"),
    "excited": ("energetic_pulse", "smiling"),
    "laughing": ("laugh_shake", "laughing"),
    "sad": ("soft_sad", "sad"),
    "crying": ("tear_fall", "crying_tears"),
    "confused": ("confused_tilt", "confused_eyebrows"),
    "surprised": ("surprise_pop", "surprised"),
    "worried": ("worried_pulse", "worried"),
    "angry": ("controlled_red_pulse", "annoyed"),
    "annoyed": ("annoyed_tilt", "annoyed"),
    "embarrassed": ("embarrassed_glow", "shy"),
    "shy": ("shy_sway", "shy"),
    "proud": ("proud_rise", "smiling"),
    "curious": ("curious_orbit", "confused_eyebrows"),
    "caring": ("warm_breathe", "smiling"),
    "serious": ("steady_focus", "serious"),
    "sleepy": ("sleepy_drift", "sleepy"),
    "thinking": ("thinking_orbit", "thinking"),
    "scared": ("fear_tremble", "worried"),
    "disappointed": ("disappointed_fade", "sad"),
}


def get_avatar_animation(emotion: str, intensity: float = 0.5) -> dict:
    animation, expression = _AVATAR.get(emotion, _AVATAR["neutral"])
    return {
        "animation": animation,
        "expression": expression,
        "animation_speed": round(0.65 + max(0.0, min(1.0, intensity)) * 0.7, 2),
        "blink_animation": "natural_blink",
    }
