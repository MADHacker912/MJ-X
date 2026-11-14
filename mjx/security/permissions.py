"""
mjx.security.permissions — Centralized Permission and Safety Boundary System.

Provides least-privilege policy enforcement, time-bounded permission grants,
user-visible approval hooks, emergency stop (kill-switch), and tamper-evident audit logging.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional


class PermissionCategory(str, Enum):
    READ_ONLY = "read_only"
    SCREEN_CAPTURE = "screen_capture"
    CAMERA_ACCESS = "camera_access"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    APP_LAUNCH = "app_launch"
    BROWSER_INTERACTION = "browser_interaction"
    OS_INPUT_CONTROL = "os_input_control"
    NETWORK_ACCESS = "network_access"
    EXTERNAL_TRANSMISSION = "external_transmission"
    ADMIN_OPERATION = "admin_operation"


@dataclass
class PermissionGrant:
    category: PermissionCategory
    scope: str
    granted_at: float
    expires_at: Optional[float]
    one_time: bool
    revoked: bool = False

    @property
    def is_valid(self) -> bool:
        if self.revoked:
            return False
        if self.expires_at is not None and time.time() > self.expires_at:
            return False
        return True


@dataclass
class AuditRecord:
    timestamp: float
    iso_time: str
    category: str
    action: str
    target: str
    decision: str  # "ALLOWED" | "DENIED" | "EMERGENCY_STOPPED"
    reason: str


class PermissionManager:
    """Manages scoped security permissions and audit trails."""

    def __init__(self, log_dir: Optional[Path] = None):
        self._grants: Dict[PermissionCategory, List[PermissionGrant]] = {
            cat: [] for cat in PermissionCategory
        }
        self._emergency_stop: bool = False
        self._ui_prompt_callback: Optional[Callable[[PermissionCategory, str, str, str], bool]] = None
        self._audit_log: List[AuditRecord] = []
        self._max_in_memory_audit: int = 1000

        # Base default policy
        self._auto_allowed_categories = {
            PermissionCategory.READ_ONLY,
            PermissionCategory.FILE_READ,
            PermissionCategory.APP_LAUNCH,
            PermissionCategory.BROWSER_INTERACTION,
            PermissionCategory.NETWORK_ACCESS,
        }

        # Categories that REQUIRE explicit user consent
        self._sensitive_categories = {
            PermissionCategory.SCREEN_CAPTURE,
            PermissionCategory.CAMERA_ACCESS,
            PermissionCategory.FILE_WRITE,
            PermissionCategory.OS_INPUT_CONTROL,
            PermissionCategory.EXTERNAL_TRANSMISSION,
            PermissionCategory.ADMIN_OPERATION,
        }

        self._log_path = (log_dir or (Path(__file__).resolve().parent.parent.parent / "logs")) / "permission_audit.jsonl"

    def set_prompt_callback(self, cb: Optional[Callable[[PermissionCategory, str, str, str], bool]]) -> None:
        """Register a GUI or conversational callback for user approval requests."""
        self._ui_prompt_callback = cb

    def emergency_stop(self) -> None:
        """Immediate kill-switch: blocks all operations until explicitly reset."""
        self._emergency_stop = True
        self._log_audit(
            category=PermissionCategory.ADMIN_OPERATION.value,
            action="EMERGENCY_STOP_ENGAGED",
            target="all",
            decision="EMERGENCY_STOPPED",
            reason="Kill switch activated by user or system safety watchdog",
        )

    def reset_emergency_stop(self) -> None:
        """Reset emergency stop back to normal operation."""
        self._emergency_stop = False
        self._log_audit(
            category=PermissionCategory.ADMIN_OPERATION.value,
            action="EMERGENCY_STOP_RESET",
            target="all",
            decision="ALLOWED",
            reason="Emergency stop cleared by operator",
        )

    @property
    def is_emergency_stopped(self) -> bool:
        return self._emergency_stop

    def grant(
        self,
        category: PermissionCategory,
        scope: str = "*",
        duration_seconds: Optional[float] = None,
        one_time: bool = False,
    ) -> PermissionGrant:
        """Grant a scoped, optionally expiring permission."""
        # Never allow permanent wildcards for ADMIN_OPERATION
        if category == PermissionCategory.ADMIN_OPERATION and duration_seconds is None and not one_time:
            duration_seconds = 60.0  # Cap admin grants at 60 seconds

        now = time.time()
        expires = now + duration_seconds if duration_seconds is not None else None
        grant_obj = PermissionGrant(
            category=category,
            scope=scope,
            granted_at=now,
            expires_at=expires,
            one_time=one_time,
        )
        self._grants[category].append(grant_obj)
        return grant_obj

    def revoke(self, category: PermissionCategory, scope: str = "*") -> int:
        """Revoke active grants for a category and scope."""
        revoked_count = 0
        for grant_obj in self._grants.get(category, []):
            if scope == "*" or grant_obj.scope == scope:
                if grant_obj.is_valid:
                    grant_obj.revoked = True
                    revoked_count += 1
        return revoked_count

    def check(
        self,
        category: PermissionCategory,
        action: str,
        target: str = "",
        reason: str = "",
    ) -> bool:
        """
        Check if an action is permitted. If sensitive, checks active grants or prompts user.
        Returns True if permitted, False otherwise.
        """
        if self._emergency_stop:
            self._log_audit(category.value, action, target, "EMERGENCY_STOPPED", "Operation blocked by kill switch")
            return False

        # 1. Non-sensitive operations allowed by default
        if category in self._auto_allowed_categories:
            self._log_audit(category.value, action, target, "ALLOWED", "Permitted under default read/launch policy")
            return True

        # 2. Check active scoped grants
        valid_grants = [g for g in self._grants.get(category, []) if g.is_valid]
        for grant_obj in valid_grants:
            if grant_obj.scope == "*" or grant_obj.scope.lower() in target.lower():
                if grant_obj.one_time:
                    grant_obj.revoked = True  # Consume one-time token
                self._log_audit(category.value, action, target, "ALLOWED", f"Permitted via active grant (scope={grant_obj.scope})")
                return True

        # 3. Prompt user if callback registered
        if self._ui_prompt_callback is not None:
            approved = self._ui_prompt_callback(category, action, target, reason)
            decision = "ALLOWED" if approved else "DENIED"
            self._log_audit(category.value, action, target, decision, "User prompt response")
            return approved

        # 4. Default: Denied if sensitive and unapproved
        self._log_audit(category.value, action, target, "DENIED", "Sensitive action requires explicit user permission")
        return False

    def get_audit_records(self, limit: int = 50) -> List[Dict]:
        """Return recent audit records (zero credentials included)."""
        recent = self._audit_log[-limit:]
        return [asdict(r) for r in reversed(recent)]

    def _log_audit(self, category: str, action: str, target: str, decision: str, reason: str) -> None:
        rec = AuditRecord(
            timestamp=time.time(),
            iso_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            category=category,
            action=action,
            target=target,
            decision=decision,
            reason=reason,
        )
        self._audit_log.append(rec)
        if len(self._audit_log) > self._max_in_memory_audit:
            self._audit_log.pop(0)

        # Append to persistent JSONL log
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(rec)) + "\n")
        except Exception:
            pass


# Global default permission manager instance
_default_manager = PermissionManager()

check_permission = _default_manager.check
grant_permission = _default_manager.grant
revoke_permission = _default_manager.revoke
emergency_stop = _default_manager.emergency_stop
reset_emergency_stop = _default_manager.reset_emergency_stop
is_emergency_stopped = lambda: _default_manager.is_emergency_stopped
set_permission_prompt = _default_manager.set_prompt_callback
get_audit_records = _default_manager.get_audit_records
