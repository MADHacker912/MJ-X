"""
mjx.intelligence.intent_classifier — Intent Classification for English, Hindi, and Hinglish.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class IntentType(str, Enum):
    CONVERSATIONAL = "conversational"
    MEMORY_QUERY = "memory_query"
    MEMORY_STORE = "memory_store"
    TOOL_ACTION = "tool_action"
    COMPLEX_TASK = "complex_task"
    SYSTEM_CONTROL = "system_control"
    CLARIFICATION_NEEDED = "clarification_needed"


@dataclass
class IntentResult:
    intent_type: IntentType
    confidence: float
    detected_entities: dict
    suggested_action: Optional[str] = None
    requires_planning: bool = False
    is_hinglish: bool = False


class IntentClassifier:
    """Classifies user intent across multi-lingual English/Hinglish inputs."""

    # Hinglish marker words
    _HINGLISH_MARKERS = {
        "karo", "karna", "krna", "bhai", "yaar", "kya", "kyu", "kyun",
        "kaise", "batao", "dikhao", "chaloo", "kholo", "rakho", "yaad",
        "mujhe", "apna", "mera", "meri", "chahiye", "theek", "achha"
    }

    # Intent regex patterns
    _MEMORY_STORE_PATTERNS = [
        r"(?:remember|yaad rakh(?:o|na)|note down|save (?:that|this))\b",
        r"(?:my favorite|meri pasand|mera naam|i prefer|mujhe pasand)\b",
    ]

    _MEMORY_QUERY_PATTERNS = [
        r"(?:what is my|kya hai mera|do you remember|kya tumhe yaad|batao mera)\b",
        r"(?:who am i|mein kaun hu|my preferences?)\b",
    ]

    _SYSTEM_CONTROL_PATTERNS = [
        r"(?:volume|brightness|wifi|wi-fi|bluetooth|shutdown|reboot|restart|sleep|mute)\b",
        r"(?:awaz|roshni|band karo|chalu karo)\b",
    ]

    _COMPLEX_TASK_CONNECTORS = [
        r"\band then\b", r"\baur phir\b", r"\baur uske baad\b",
        r"\bthen open\b", r"\bfirst\b.*\bthen\b",
    ]

    def classify(self, text: str) -> IntentResult:
        raw = text.strip()
        lower = raw.lower()
        words = set(re.findall(r"\w+", lower))

        # Check Hinglish
        is_hinglish = bool(words & self._HINGLISH_MARKERS)

        # 1. Complex Task Check (contains sequence chaining)
        for pat in self._COMPLEX_TASK_CONNECTORS:
            if re.search(pat, lower):
                return IntentResult(
                    intent_type=IntentType.COMPLEX_TASK,
                    confidence=0.90,
                    detected_entities={"raw_query": raw},
                    requires_planning=True,
                    is_hinglish=is_hinglish,
                )

        # 2. Memory Store Check
        for pat in self._MEMORY_STORE_PATTERNS:
            if re.search(pat, lower):
                return IntentResult(
                    intent_type=IntentType.MEMORY_STORE,
                    confidence=0.88,
                    detected_entities={"query": raw},
                    suggested_action="store_memory",
                    is_hinglish=is_hinglish,
                )

        # 3. Memory Query Check
        for pat in self._MEMORY_QUERY_PATTERNS:
            if re.search(pat, lower):
                return IntentResult(
                    intent_type=IntentType.MEMORY_QUERY,
                    confidence=0.85,
                    detected_entities={"query": raw},
                    suggested_action="search_memory",
                    is_hinglish=is_hinglish,
                )

        # 4. System Control Check
        for pat in self._SYSTEM_CONTROL_PATTERNS:
            if re.search(pat, lower):
                return IntentResult(
                    intent_type=IntentType.SYSTEM_CONTROL,
                    confidence=0.85,
                    detected_entities={"query": raw},
                    suggested_action="computer_settings",
                    is_hinglish=is_hinglish,
                )

        # 5. Tool Action vs Conversational
        tool_keywords = {
            "search", "google", "weather", "flight", "open", "launch",
            "screenshot", "photo", "camera", "calc", "calculate", "code",
            "kholo", "dhundo", "mausam"
        }
        if words & tool_keywords:
            return IntentResult(
                intent_type=IntentType.TOOL_ACTION,
                confidence=0.80,
                detected_entities={"keywords": list(words & tool_keywords)},
                is_hinglish=is_hinglish,
            )

        # Default: Conversational
        return IntentResult(
            intent_type=IntentType.CONVERSATIONAL,
            confidence=0.75,
            detected_entities={},
            is_hinglish=is_hinglish,
        )
