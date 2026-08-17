"""Truthfulness and fake-validation guardrails."""

from __future__ import annotations

import re


_FAKE_PRAISE = re.compile(r"\b(?:amazing idea|absolutely right|perfect|great job|brilliant)\b", re.I)
_FALSE_ACTION = re.compile(r"\b(?:i (?:have|successfully) (?:opened|sent|deleted|installed|completed))\b", re.I)


class TruthfulnessGuard:
    @staticmethod
    def prompt_guidance(fake_praise_blocked: bool = True) -> str:
        praise = (
            "Praise only when earned and name the specific strength; never use generic validation."
            if fake_praise_blocked else "Keep praise proportionate and specific."
        )
        return (
            "Do not blindly agree. Distinguish emotional support from factual agreement. "
            "When uncertain, say what is unknown and verify with tools instead of inventing. "
            "Never claim an action succeeded unless its tool result confirms success. " + praise
        )

    @staticmethod
    def review_generated_text(text: str) -> list[str]:
        warnings: list[str] = []
        if _FAKE_PRAISE.search(text):
            warnings.append("possible_generic_praise")
        if _FALSE_ACTION.search(text):
            warnings.append("verify_action_claim_against_tool_result")
        return warnings

