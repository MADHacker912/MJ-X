"""
mjx.emotions.response_style — Adapts Linguistic Style, Tone, and Contextual Interaction Modes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class StyleProfile:
    formality: str      # "casual", "neutral", "formal"
    pace: str           # "fast", "medium", "gentle", "slow"
    empathy_level: str  # "high", "moderate", "neutral"
    emoji_allowed: bool
    prefix_hint: str


@dataclass
class AdaptationProfile:
    name: str
    description: str
    guidance: str
    clarity_priority: str
    pacing: str


EMOTION_STYLES = {
    "happy": StyleProfile("casual", "fast", "moderate", True, "🎉 "),
    "excited": StyleProfile("casual", "fast", "moderate", True, "⚡ "),
    "laughing": StyleProfile("casual", "fast", "moderate", True, "😄 "),
    "proud": StyleProfile("casual", "medium", "high", True, "🌟 "),
    "sad": StyleProfile("neutral", "gentle", "high", False, "Main samajh sakta hu. "),
    "crying": StyleProfile("neutral", "gentle", "high", False, "Shant ho jaiye, main yahi hu. "),
    "worried": StyleProfile("neutral", "medium", "high", False, "Fikar mat kijiye, hum milkar solve karenge. "),
    "annoyed": StyleProfile("neutral", "fast", "moderate", False, "Let's fix this right away. "),
    "angry": StyleProfile("formal", "medium", "moderate", False, "I hear your frustration. Let's address this directly. "),
    "confused": StyleProfile("neutral", "medium", "moderate", False, "Step-by-step samajhte hain: "),
    "serious": StyleProfile("formal", "medium", "high", False, ""),
    "sleepy": StyleProfile("casual", "slow", "moderate", False, "Aap aaram se dekhiye. "),
    "curious": StyleProfile("casual", "medium", "moderate", False, ""),
    "thinking": StyleProfile("neutral", "medium", "neutral", False, ""),
    "surprised": StyleProfile("casual", "fast", "moderate", False, ""),
    "scared": StyleProfile("neutral", "gentle", "high", False, "Stay calm, safety is first. "),
    "disappointed": StyleProfile("neutral", "gentle", "moderate", False, "Koi baat nahi, we can rebuild. "),
    "caring": StyleProfile("neutral", "gentle", "high", False, "Take care. "),
    "neutral": StyleProfile("neutral", "medium", "neutral", False, ""),
}


INTERACTION_STYLES: Dict[str, AdaptationProfile] = {
    "technical_explanation": AdaptationProfile(
        name="Technical Explanation",
        description="Structured, precise, and logically sequenced architectural explanation.",
        guidance="Present clear, structured, precise explanations. Focus on root causes, architecture, invariants, and step-by-step logic without conversational fluff.",
        clarity_priority="high",
        pacing="steady",
    ),
    "casual_conversation": AdaptationProfile(
        name="Casual Conversation",
        description="Warm, natural, and friendly peer exchange.",
        guidance="Maintain a warm, relaxed, natural conversational cadence with appropriate Hinglish/English phrasing, natural wit, and approachable peer tone.",
        clarity_priority="medium",
        pacing="lively",
    ),
    "learning_assistance": AdaptationProfile(
        name="Learning Assistance",
        description="Supportive pedagogical breakdown with analogies and comprehension checks.",
        guidance="Be encouraging and pedagogical. Break down complex concepts into digestible steps, offer intuitive analogies, and verify understanding.",
        clarity_priority="high",
        pacing="gentle",
    ),
    "brainstorming": AdaptationProfile(
        name="Brainstorming",
        description="Divergent creative thinking with constructive challenge and options.",
        guidance="Be creative and exploratory. Propose diverse alternatives, weigh trade-offs, explore unconventional angles, and ask constructive probing questions.",
        clarity_priority="high",
        pacing="energetic",
    ),
    "task_execution": AdaptationProfile(
        name="Task Execution",
        description="Action-oriented, minimal, status-driven execution feedback.",
        guidance="Be direct, action-focused, and concise. State parameters, execution status, and results clearly with zero unnecessary filler or chit-chat.",
        clarity_priority="maximum",
        pacing="crisp",
    ),
    "error_communication": AdaptationProfile(
        name="Error Communication",
        description="Calm, empathetic, solution-oriented de-escalation of failures.",
        guidance="Be calm, supportive, and solution-focused. Acknowledge the issue clearly, avoid blaming the user, explain the failure plainly, and provide immediate remediation steps.",
        clarity_priority="high",
        pacing="deliberate",
    ),
}

_TECH_REGEX = re.compile(r"\b(?:architecture|algorithm|schema|database|function|class|api|pipeline|latency|memory|thread|async|mutex|sql|sqlite|compiler|debug|traceback|regex)\b", re.I)
_LEARN_REGEX = re.compile(r"\b(?:teach|explain to me|how does.*work|what is the meaning|concept|understand|basics of|beginner|step by step)\b", re.I)
_BRAIN_REGEX = re.compile(r"\b(?:brainstorm|ideas|options|alternatives|what if|suggestions|creative|explore|pros and cons|opinions)\b", re.I)
_TASK_REGEX = re.compile(r"\b(?:open|close|run|execute|delete|search|find|set|calculate|send|save|build|download)\b", re.I)
_ERROR_REGEX = re.compile(r"\b(?:error|crash|exception|failed|failure|broken|not working|nahi chal raha|bug|issue|fatal)\b", re.I)


class ResponseStyleAdapter:
    """Modulates output phrasing and system prompt guidance based on active emotional state and interaction style."""

    def __init__(self, emoji_enabled: bool = False):
        self.emoji_enabled = emoji_enabled

    def get_style_profile(self, emotion: str) -> StyleProfile:
        return EMOTION_STYLES.get(emotion, EMOTION_STYLES["neutral"])

    def get_adaptation_style(self, style_name: str) -> AdaptationProfile:
        return INTERACTION_STYLES.get(style_name, INTERACTION_STYLES["casual_conversation"])

    def detect_interaction_style(self, text: str, history: Optional[List[str]] = None) -> str:
        """Determines the most appropriate interaction mode for the given query."""
        content = (text or "").strip()
        if not content:
            return "casual_conversation"

        if _ERROR_REGEX.search(content):
            return "error_communication"
        if _LEARN_REGEX.search(content):
            return "learning_assistance"
        if _BRAIN_REGEX.search(content):
            return "brainstorming"
        if _TECH_REGEX.search(content):
            return "technical_explanation"
        if _TASK_REGEX.search(content) and len(content.split()) <= 8:
            return "task_execution"

        return "casual_conversation"

    def adapt_message(self, text: str, emotion: str, intensity: float = 0.5) -> str:
        profile = self.get_style_profile(emotion)
        content = text.strip()

        # Add empathetic prefix cues for distressing states when intensity is significant
        if profile.prefix_hint and not content.startswith(profile.prefix_hint.strip()):
            if emotion in {"sad", "crying", "worried", "angry"} and intensity >= 0.6:
                content = f"{profile.prefix_hint}{content}"
            elif profile.emoji_allowed and self.emoji_enabled and intensity >= 0.7:
                content = f"{profile.prefix_hint}{content}"

        return content

    def get_prompt_guidance(self, emotion: str, interaction_style: str, intensity: float = 0.5) -> str:
        """Constructs safe, non-anthropomorphic presentation instructions for Gemini."""
        emo_profile = self.get_style_profile(emotion)
        adapt_profile = self.get_adaptation_style(interaction_style)

        return (
            "[CONVERSATIONAL & EMOTION PRESENTATION STYLE]\n"
            f"- Active Presentation Tone: {emotion} (intensity {intensity:.2f}, pace: {emo_profile.pace})\n"
            f"- Interaction Mode: {adapt_profile.name} — {adapt_profile.guidance}\n"
            f"- Clarity Standard: {adapt_profile.clarity_priority}\n"
            "- Boundary Mandate: This controls rhetorical clarity, tone, and pacing only. "
            "Never pretend to possess biological feelings, fabricate emotional experiences, or manipulate the user."
        )
