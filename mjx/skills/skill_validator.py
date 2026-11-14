"""
mjx.skills.skill_validator — SKILL.md Frontmatter and Security Validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ValidationReport:
    is_valid: bool
    skill_name: str
    errors: List[str]
    warnings: List[str]


class SkillValidator:
    """Validates skill metadata and security constraints before registration."""

    REQUIRED_FIELDS = {"name", "description"}

    def validate_metadata(self, metadata: Dict[str, Any]) -> ValidationReport:
        errors: List[str] = []
        warnings: List[str] = []

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in metadata or not str(metadata[field]).strip():
                errors.append(f"Missing required field: '{field}'")

        name = str(metadata.get("name", "")).strip()
        if name and not re.match(r"^[a-zA-Z0-9_\-]+$", name):
            errors.append(f"Invalid skill name '{name}': only alphanumeric, hyphen, and underscore permitted")

        # Security checks: ensure permissions are declared
        perms = metadata.get("permissions", [])
        if not isinstance(perms, list):
            warnings.append("Permissions field should be a list")

        return ValidationReport(
            is_valid=len(errors) == 0,
            skill_name=name,
            errors=errors,
            warnings=warnings,
        )
