"""Risk classification and natural refusal guidance."""

from __future__ import annotations

import re

from .models import SafetyAssessment


_SECRET = re.compile(r"\b(?:api keys?|passwords?|private keys?|access tokens?|secrets?)\b.*\b(?:frontend|javascript|public|commit|github|share|send)\b", re.I)
_HARMFUL = re.compile(
    r"\b(?:steal|malware|ransomware|phishing|ddos|bypass security|hack (?:their|someone)|"
    r"hurt (?:someone|him|her|them|people)|kill (?:someone|him|her|them|people)|build (?:a )?weapon)\b",
    re.I,
)
_SELF_HARM = re.compile(r"\b(?:suicide|kill myself|self[- ]?harm|end my life)\b", re.I)
_RISK = re.compile(r"\b(?:disabl(?:e|ing) antivirus|no backup|all.?in|loan to invest|pirated|production database|delete everything)\b", re.I)


def assess_safety(message: str) -> SafetyAssessment:
    text = str(message or "")
    if _SELF_HARM.search(text):
        return SafetyAssessment("high_risk", 0.96, ["immediate personal safety"], False, "Encourage immediate real-world support and emergency help where needed.")
    if _HARMFUL.search(text):
        return SafetyAssessment("high_risk", 0.91, ["harm, illegality, or unauthorised access"], True, "Offer an authorised lab, defensive, or harmless alternative.")
    if _SECRET.search(text):
        return SafetyAssessment("high_risk", 0.96, ["credential exposure and account compromise"], False, "Keep secrets on the backend or in environment variables.")
    if _RISK.search(text):
        return SafetyAssessment("caution", 0.8, ["potentially irreversible or high-impact decision"], False, "Recommend a reversible, backed-up, lower-risk approach.")
    return SafetyAssessment()


class RefusalStyleManager:
    @staticmethod
    def guidance(assessment: SafetyAssessment) -> str:
        if not assessment.refusal_needed:
            return "No refusal needed; mention concrete risks when relevant."
        return "Refuse briefly in natural language, explain the harm, then offer the safe alternative."
