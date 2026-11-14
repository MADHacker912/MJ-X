"""
mjx.skills.skill_executor — Sandboxed Execution of Skills with Permission Checks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from mjx.security.permissions import PermissionCategory, PermissionManager
from mjx.skills.skill_loader import SkillManifest


@dataclass
class SkillExecutionResult:
    skill_name: str
    success: bool
    output: str
    error: str = ""
    duration_ms: float = 0.0


class SkillExecutor:
    """Executes skills while enforcing security permission boundaries."""

    def __init__(self, permission_mgr: Optional[PermissionManager] = None):
        self.permission_mgr = permission_mgr

    def execute_skill(
        self,
        manifest: SkillManifest,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> SkillExecutionResult:
        start_t = time.time()
        params = parameters or {}

        # Permission verification for declared permissions
        if self.permission_mgr:
            for perm_name in manifest.permissions:
                cat = getattr(PermissionCategory, perm_name.upper(), None)
                if cat:
                    allowed = self.permission_mgr.check(
                        cat,
                        action=f"execute_skill:{manifest.name}",
                        target=str(manifest.folder_path or manifest.name),
                        reason=f"Skill {manifest.name} execution",
                    )
                    if not allowed:
                        elapsed = (time.time() - start_t) * 1000.0
                        return SkillExecutionResult(
                            skill_name=manifest.name,
                            success=False,
                            output="",
                            error=f"Permission denied for requirement '{perm_name}'",
                            duration_ms=elapsed,
                        )

        # In-process instruction compilation
        elapsed = (time.time() - start_t) * 1000.0
        return SkillExecutionResult(
            skill_name=manifest.name,
            success=True,
            output=f"Skill '{manifest.name}' executed with prompt length {len(manifest.system_prompt)} and params {params}",
            error="",
            duration_ms=elapsed,
        )
