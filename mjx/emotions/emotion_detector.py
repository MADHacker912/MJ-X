"""
mjx.emotions.emotion_detector — Multi-Modal Linguistic and Contextual Emotion Detection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DetectionResult:
    emotion: str
    intensity: float
    confidence: float
    valence: float
    arousal: float
    reason: str


# Keyword patterns for Hinglish + English conversational cues
EMOTION_PATTERNS = {
    "laughing": [
        r"(😂|🤣|lol|lmao|rofl|hahaha|hehe|bohot funny|has has ke)",
    ],
    "happy": [
        r"(great|awesome|badhiya|shandar|mast|yay|khush|bohot accha|feeling good|party)",
    ],
    "excited": [
        r"(excited|thrilled|super pumped|can't wait|cannot wait|dhamaka|maza aayega|woohoo)",
    ],
    "proud": [
        r"(cleared.*exam|passed|won|achieved|jeet gaya|crack kar liya|top kiya|certified)",
    ],
    "worried": [
        r"(worried|tension|chinta|urgent error|panic|dar lag raha|phas gaya|help please)",
    ],
    "confused": [
        r"(confused|kya matlab|samajh nahi aaya|what do you mean|\?\?\?|how does this work)",
    ],
    "sad": [
        r"(sad|dukh|dard|depressed|feeling low|cry|😭|dard ho raha|dil toot gaya)",
    ],
    "crying": [
        r"(crying|ro raha|rona aa raha|shed tears|sobbing|too hurt)",
    ],
    "annoyed": [
        r"(again and again|baar baar|annoying|frustrated|dimag kharab|bakwas|irritating)",
    ],
    "angry": [
        r"(angry|gussa|krodh|furious|shut up|bakwas band karo|hate this)",
    ],
    "scared": [
        r"(scared|terrified|dar gaya|frightened|horror|creepy)",
    ],
    "disappointed": [
        r"(disappointed|letdown|nirash|ummeed toot gayi|bekaar ho gaya|failed again)",
    ],
    "sleepy": [
        r"(sleepy|tired|exhausted|thak gaya|neend|so raha hu|yawning)",
    ],
    "curious": [
        r"(wondering|curious|batao zara|kaise hua|explain|deep dive)",
    ],
    "caring": [
        r"(take care|dhyaan rakhna|hope you are well|khayal rakhna|worry about you)",
    ],
    "thinking": [
        r"(thinking|let me think|soch raha hu|pondering|hmm\b)",
    ],
    "surprised": [
        r"(surprised|shocked|what the|are you serious|sach me|unexpected|arre baap re)",
    ],
    "serious": [
        r"(serious|critical|incident|died|hospital|emergency|loss)",
    ],
}


class ContextualEmotionDetector:
    """Detects emotion with contextual history and Hinglish awareness."""

    def __init__(self):
        self._compiled = {
            emo: [re.compile(p, re.IGNORECASE) for p in patterns]
            for emo, patterns in EMOTION_PATTERNS.items()
        }

    def detect(self, text: str, history: Optional[List[str]] = None) -> DetectionResult:
        content = (text or "").strip()
        if not content:
            return DetectionResult("neutral", 0.5, 0.9, 0.0, 0.0, "Empty input")

        # 1. Serious incident check
        for pat in self._compiled["serious"]:
            if pat.search(content):
                return DetectionResult("serious", 0.7, 0.9, -0.6, 0.2, "Serious incident keywords")

        # 2. Check repetition in history (e.g. repeated failure -> annoyed)
        if history and len(history) >= 2:
            recent_errors = sum(1 for h in history[-3:] if "error" in str(h).lower() or "fail" in str(h).lower())
            if recent_errors >= 2 and ("error" in content.lower() or "baar" in content.lower()):
                return DetectionResult("annoyed", 0.75, 0.85, -0.5, 0.4, "Repeated failures in context")

        # 3. Check regex match rankings
        for emo, pats in self._compiled.items():
            for p in pats:
                if p.search(content):
                    valence = 0.6 if emo in {"happy", "laughing", "proud", "excited"} else (-0.5 if emo in {"sad", "worried", "annoyed", "angry", "crying", "scared", "disappointed"} else 0.0)
                    arousal = 0.7 if emo in {"laughing", "excited", "worried", "annoyed", "angry", "surprised"} else (-0.4 if emo in {"sleepy", "sad", "thinking"} else 0.1)
                    return DetectionResult(
                        emotion=emo,
                        intensity=0.75,
                        confidence=0.85,
                        valence=valence,
                        arousal=arousal,
                        reason=f"Matched pattern for {emo}",
                    )

        # Default fallback
        return DetectionResult("neutral", 0.5, 0.7, 0.0, 0.0, "Default neutral baseline")
