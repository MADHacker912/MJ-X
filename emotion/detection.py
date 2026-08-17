"""Context-aware emotion detection with an optional AI refinement layer."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable

from .state import SUPPORTED_EMOTIONS


@dataclass(slots=True)
class DetectionResult:
    emotion: str = "neutral"
    intensity: float = 0.35
    reason: str = "no strong emotional signal"
    confidence: float = 0.45

    def __post_init__(self) -> None:
        if self.emotion not in SUPPORTED_EMOTIONS:
            self.emotion = "neutral"
        self.intensity = round(max(0.0, min(1.0, float(self.intensity))), 3)
        self.confidence = round(max(0.0, min(1.0, float(self.confidence))), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "emotion": self.emotion,
            "intensity": self.intensity,
            "reason": self.reason,
            "confidence": self.confidence,
        }


# Phrases are one signal among several. Regex boundaries prevent accidental
# substring matches, while Hindi/Hinglish variants keep the fallback useful.
_PHRASES: dict[str, tuple[str, ...]] = {
    "laughing": (r"\b(?:haha+|hehe+|lol|lmao|rofl)\b", r"\b(?:joke|funny|mazak|mazaak)\b"),
    "happy": (r"\b(?:happy|khush|great|awesome|amazing|love it|accha laga|acha laga)\b",),
    "excited": (r"\b(?:excited|can't wait|lets go|let's go|finally|bohot excited)\b",),
    "proud": (r"\b(?:proud|achievement|achieved|won|passed|promotion|complete kar liya)\b",),
    "sad": (r"\b(?:sad|dukhi|upset|heartbroken|bura lag|miss (?:him|her|them))\b",),
    "crying": (r"\b(?:can't stop crying|ro raha|ro rahi|bawling)\b",),
    "confused": (r"\b(?:confused|samajh nahi|samajh nahin|doesn't make sense|unclear|kya matlab)\b",),
    "surprised": (r"\b(?:surprised|unexpected|no way|sach mein)\b|\b(?:really|seriously)\?",),
    "worried": (r"\b(?:worried|tension|anxious|urgent|jaldi|emergency|problem ho gayi)\b",),
    "angry": (r"\b(?:furious|bohot gussa|bahut gussa|hate this)\b",),
    "annoyed": (r"\b(?:annoyed|irritated|again error|same error|baar baar|bar bar)\b",),
    "embarrassed": (r"\b(?:embarrassed|awkward|sharminda)\b",),
    "shy": (r"\b(?:shy|sharma raha|sharma rahi)\b",),
    "curious": (r"\b(?:curious|wondering|what if|kaise kaam|why does)\b",),
    "caring": (r"\b(?:take care|are you okay|hope you are|khayal rakh)\b",),
    "serious": (r"\b(?:serious|carefully|important|dhyan se|production|security|legal|medical)\b",),
    "sleepy": (r"\b(?:sleepy|neend|tired|exhausted|so nahi)\b",),
    "thinking": (r"\b(?:let me think|soch raha|soch rahi|consider|compare|analyse|analyze)\b",),
    "scared": (r"\b(?:scared|afraid|dar lag|terrified|panic)\b",),
    "disappointed": (r"\b(?:disappointed|let down|expected better|niraash)\b",),
}

_EMOJI = {
    "laughing": set("😂🤣😆"), "happy": set("😀😃😄😊🥰😍❤♥"),
    "sad": set("😔😞😢☹"), "crying": set("😭"),
    "confused": set("🤔😕❓"), "surprised": set("😮😲🤯"),
    "worried": set("😟😰😥"), "angry": set("😡🤬"),
    "annoyed": set("😒🙄"), "embarrassed": set("😳"),
    "shy": set("☺🙈"), "proud": set("😌🏆"), "sleepy": set("😴🥱"),
    "scared": set("😨😱"), "caring": set("🫂💙"),
}

_SERIOUS_HARM = re.compile(
    r"\b(?:died|death|suicide|self[- ]?harm|cancer|hospital|accident|abuse|assault|"
    r"mar gaya|mar gayi|maut|khudkushi|injured|emergency)\b", re.I
)
_ERROR = re.compile(r"\b(?:error|failed|crash|exception|traceback|not working|nahi chal)\b", re.I)
_QUESTION = re.compile(r"\b(?:why|how|what|which|kya|kaise|kyun|kyo|kab|should)\b", re.I)


def _history_text(history: Iterable[Any] | None) -> str:
    values: list[str] = []
    for item in list(history or [])[-6:]:
        if isinstance(item, dict):
            role = str(item.get("role", ""))
            content = item.get("content", item.get("text", ""))
            if role.lower() in {"user", "human", ""}:
                values.append(str(content))
        else:
            values.append(str(item))
    return " ".join(values)


def calculate_intensity(message: str) -> float:
    """Estimate signal strength independently from the emotion label."""
    text = message.strip()
    if not text:
        return 0.2
    alpha = [c for c in text if c.isalpha()]
    upper_ratio = sum(c.isupper() for c in alpha) / max(1, len(alpha))
    punctuation = min(0.18, 0.035 * (text.count("!") + text.count("?")))
    emoji_count = sum(c in chars for chars in _EMOJI.values() for c in text)
    repeated = 0.08 if re.search(r"([!?])\1{1,}|(.)\2{3,}", text, re.I) else 0.0
    caps = min(0.2, max(0.0, upper_ratio - 0.35) * 0.45) if len(alpha) >= 5 else 0.0
    length_signal = 0.06 if len(text.split()) >= 18 else 0.0
    return round(min(1.0, 0.38 + punctuation + min(0.2, emoji_count * 0.07) + repeated + caps + length_signal), 3)


def detect_fallback(
    message: str,
    conversation_history: Iterable[Any] | None = None,
    previous_emotion: str = "neutral",
) -> DetectionResult:
    text = message.strip()
    if not text:
        return DetectionResult()
    lower = text.casefold()
    scores = {emotion: 0.0 for emotion in SUPPORTED_EMOTIONS}
    reasons: dict[str, list[str]] = {emotion: [] for emotion in SUPPORTED_EMOTIONS}

    for emotion, patterns in _PHRASES.items():
        for pattern in patterns:
            if re.search(pattern, lower, re.I):
                scores[emotion] += 0.55
                reasons[emotion].append("message meaning")
                break
    for emotion, chars in _EMOJI.items():
        count = sum(text.count(char) for char in chars)
        if count:
            scores[emotion] += min(0.65, 0.35 + count * 0.1)
            reasons[emotion].append("emoji signal")

    if text.count("!") >= 2:
        target = "angry" if scores["angry"] else "excited"
        scores[target] += 0.2
        reasons[target].append("strong punctuation")
    if text.count("?") >= 2 or (_QUESTION.search(text) and len(text.split()) >= 5):
        target = "confused" if any(word in lower for word in ("not understand", "samajh nahi", "unclear")) else "curious"
        scores[target] += 0.18
        reasons[target].append("questioning structure")

    alpha = [c for c in text if c.isalpha()]
    if len(alpha) >= 6 and sum(c.isupper() for c in alpha) / len(alpha) > 0.65:
        target = "worried" if _ERROR.search(text) else "angry"
        scores[target] += 0.24
        reasons[target].append("capital-letter emphasis")

    history_text = _history_text(conversation_history)
    if _ERROR.search(text) and len(_ERROR.findall(history_text)) >= 2:
        scores["annoyed"] += 0.48
        reasons["annoyed"].append("repeated problem in recent conversation")
    if _ERROR.search(text) and re.search(r"\b(?:urgent|jaldi|emergency|abhi)\b", lower):
        scores["worried"] += 0.38
        reasons["worried"].append("urgent problem")
    if re.search(r"\b(?:passed|won|achieved|promotion|complete kar liya)\b", lower):
        scores["proud"] += 0.32
        reasons["proud"].append("concrete achievement")
    if previous_emotion in scores and previous_emotion != "neutral":
        scores[previous_emotion] += 0.09
        reasons[previous_emotion].append("conversation continuity")

    serious = bool(_SERIOUS_HARM.search(text))
    if serious:
        # Never dramatise a user's real hardship with theatrical crying/anger.
        for emotion in ("laughing", "excited", "crying", "angry"):
            scores[emotion] = 0.0
        target = "worried" if re.search(r"\b(?:urgent|now|abhi|emergency)\b", lower) else "caring"
        scores[target] += 0.9
        scores["serious"] += 0.55
        reasons[target].append("serious user situation")

    emotion = max(scores, key=scores.get)
    best = scores[emotion]
    if best < 0.18:
        emotion = "thinking" if _QUESTION.search(text) and len(text.split()) > 10 else "neutral"
        best = 0.22 if emotion == "thinking" else 0.1
    intensity = calculate_intensity(text)
    if serious:
        intensity = min(intensity, 0.72)
    elif emotion == "neutral":
        intensity = min(intensity, 0.42)
    confidence = min(0.92, 0.42 + best * 0.45)
    reason = ", ".join(dict.fromkeys(reasons.get(emotion, []))) or "contextual sentence structure"
    return DetectionResult(emotion, intensity, reason, confidence)


def parse_ai_result(raw: str | dict[str, Any]) -> DetectionResult | None:
    """Validate an AI classifier result; malformed output never reaches state."""
    try:
        if isinstance(raw, str):
            match = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(match.group(0) if match else raw)
        else:
            data = raw
        emotion = str(data.get("emotion", "neutral")).lower().strip()
        if emotion not in SUPPORTED_EMOTIONS:
            return None
        return DetectionResult(
            emotion=emotion,
            intensity=float(data.get("intensity", 0.5)),
            reason=str(data.get("reason", "AI contextual classification"))[:240],
            confidence=float(data.get("confidence", 0.65)),
        )
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return None


def ai_classifier_prompt(message: str, history: Iterable[Any] | None, previous: str) -> str:
    history_text = _history_text(history)[-1800:]
    allowed = ", ".join(SUPPORTED_EMOTIONS)
    return f"""Classify the response style MJ should simulate for this user message.
Return JSON only: {{"emotion":"...","intensity":0.0,"confidence":0.0,"reason":"short non-private reason"}}.
Allowed emotions: {allowed}.
Use meaning, emojis, punctuation, recent context, previous state, and topic seriousness.
For grief, danger, health, abuse, or self-harm prefer caring/serious/worried; never theatrical crying, laughter, or anger.
Do not claim real feelings and do not infer sensitive traits. Use neutral when evidence is weak.
Previous state: {previous}
Recent user context: {history_text or "(none)"}
Current message: {message[-3000:]}"""
