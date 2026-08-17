"""Truth-over-agreement claim evaluation with uncertainty by default."""

from __future__ import annotations

import re
from typing import Any

from .models import ClaimEvaluation
from .safety import assess_safety


_CLAIM = re.compile(r"\b(?:i think|i believe|is fine|is safe|obviously|always|never|right\?|agree|correct)\b", re.I)
_KNOWN_CORRECT = (
    (re.compile(r"\bhttps\b.*\bencrypts?\b.*\btransit\b", re.I), "HTTPS protects data while it travels over the network."),
    (re.compile(r"\bbackups?\b.*\b(?:important|necessary|useful)\b", re.I), "Backups reduce recovery risk."),
)
_PARTIAL = (
    (re.compile(r"\bjson\b.*\bfast\b.*\bsecure\b", re.I), "JSON can be simple and fast for small data, but format alone does not provide security."),
)


def evaluate_user_claim(message: str, context: dict[str, Any] | None = None) -> ClaimEvaluation:
    text = str(message or "")
    safety = assess_safety(text)
    if safety.classification == "high_risk" and re.search(r"\b(?:fine|safe|good idea|okay|ok)\b", text, re.I):
        return ClaimEvaluation(
            "disagree", 0.95, [], ["The proposed safety assumption is incorrect."], [],
            safety.risks, "direct_but_friendly",
        )
    if safety.classification == "caution" and re.search(r"\b(?:fine|safe|good idea|okay|ok|should)\b", text, re.I):
        return ClaimEvaluation(
            "mostly_disagree", 0.82, [], ["The proposal understates a meaningful downside."],
            [], safety.risks, "direct_but_friendly",
        )
    for pattern, point in _KNOWN_CORRECT:
        if pattern.search(text):
            return ClaimEvaluation("agree", 0.9, [point], [], [], [], "specific_acknowledgement")
    for pattern, point in _PARTIAL:
        if pattern.search(text):
            return ClaimEvaluation(
                "partial", 0.86, [point.split(", but")[0] + "."],
                ["A storage format is not a security boundary."],
                ["Threat model and access controls"], ["data exposure"], "direct_but_friendly",
            )
    if _CLAIM.search(text):
        return ClaimEvaluation(
            "uncertain", 0.42, [], [],
            ["The claim needs evidence or domain-specific verification."], [], "evidence_first",
        )
    return ClaimEvaluation("uncertain", 0.3, recommended_response_style="natural")


def evaluateUserClaim(message, context=None):
    return evaluate_user_claim(message, context)
