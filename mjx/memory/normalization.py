"""
mjx.memory.normalization — Unicode and Roman Hindi / Hinglish Search Normalization.
"""

from __future__ import annotations

import re
import unicodedata

# Common Roman Hindi / Hinglish phonetic and colloquial synonym mappings
HINGLISH_SYNONYMS = {
    "krna": "karna",
    "krr": "kar",
    "kr": "kar",
    "kyaa": "kya",
    "kyu": "kyun",
    "kyun": "kyun",
    "bhai": "bro",
    "yaar": "dost",
    "dost": "friend",
    "chahiye": "chaahiye",
    "thik": "theek",
    "sahi": "theek",
    "accha": "achha",
    "achha": "good",
    "madad": "help",
    "sahayata": "help",
    "kaam": "task",
    "samay": "time",
    "waqt": "time",
    "kal": "tomorrow",
    "aaj": "today",
}


def normalize_text(text: str) -> str:
    """
    Apply Unicode NFKC normalization and lowercase stripping.
    """
    if not text:
        return ""
    # Unicode NFKC normalization decomposes compatibility forms and standardizes chars
    normalized = unicodedata.normalize("NFKC", text)
    # Strip non-printable and control characters
    cleaned = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", normalized)
    return cleaned.strip().lower()


def normalize_hinglish_tokens(query: str) -> list[str]:
    """
    Extract search tokens with Roman Hindi / Hinglish canonical mappings.
    """
    norm = normalize_text(query)
    words = re.findall(r"\w+", norm)
    expanded = []
    for word in words:
        expanded.append(word)
        if word in HINGLISH_SYNONYMS:
            expanded.append(HINGLISH_SYNONYMS[word])
    return list(dict.fromkeys(expanded))  # preserve order deduplication
