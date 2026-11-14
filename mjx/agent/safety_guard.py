"""
mjx.agent.safety_guard — Safe Zones, Sensitive Window Protection, and Action Vetoing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from mjx.security.permissions import PermissionCategory, PermissionManager


# High-risk keywords or window titles that require explicit user veto/confirmation
PROTECTED_WINDOW_PATTERNS = [
    r"password", r"credential", r"bank", r"payment", r"checkout",
    r"crypto", r"wallet", r"terminal", r"sudo", r"root",
]


@dataclass
class SafetyCheckResult:
    allowed: bool
    reason: str
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"


class AgentSafetyGuard:
    """Guards desktop agent execution from touching prohibited controls or destructive flows."""

    def __init__(self, permission_mgr: Optional[PermissionManager] = None):
        self.perm_mgr = permission_mgr
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in PROTECTED_WINDOW_PATTERNS]

    def validate_action(
        self,
        action_type: str,
        target_description: str = "",
        window_title: str = "",
        coordinates: Optional[tuple[int, int]] = None,
    ) -> SafetyCheckResult:
        # 1. Emergency stop check
        if self.perm_mgr and self.perm_mgr.is_emergency_stopped:
            return SafetyCheckResult(False, "Execution halted by Emergency Stop Kill Switch", "CRITICAL")

        # 2. Check window title for sensitive financial or security inputs
        if window_title:
            for pat in self._compiled_patterns:
                if pat.search(window_title):
                    return SafetyCheckResult(
                        False,
                        f"Action blocked: Active window '{window_title}' is protected against automated interaction",
                        "HIGH",
                    )

        # 3. Check destructive keywords in target description or typed text
        dangerous_keywords = ["rm -rf", "format", "drop table", "mkfs", "delete all", "wipe disk"]
        desc_lower = target_description.lower()
        for kw in dangerous_keywords:
            if kw in desc_lower:
                return SafetyCheckResult(
                    False,
                    f"Action blocked: High risk destructive command detected: '{kw}'",
                    "CRITICAL",
                )

        # 4. Check OS Input Control Permission
        if self.perm_mgr:
            allowed = self.perm_mgr.check(
                PermissionCategory.OS_INPUT_CONTROL,
                action=action_type,
                target=target_description,
                reason="Desktop Agent Action",
            )
            if not allowed:
                return SafetyCheckResult(False, f"Permission denied for OS input control: {action_type}", "HIGH")

        return SafetyCheckResult(True, "Action verified and safe to execute", "LOW")
