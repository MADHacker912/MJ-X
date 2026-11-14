"""
mjx.skills.skill_registry — Indexing and Lifecycle Management for Skills.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from mjx.skills.skill_loader import SkillManifest
from mjx.skills.skill_validator import SkillValidator


class SkillRegistry:
    """Manages registered skills with keyword-based lookup and capability indexing."""

    def __init__(self):
        self._skills: Dict[str, SkillManifest] = {}
        self._validator = SkillValidator()

    def register(self, manifest: SkillManifest) -> bool:
        report = self._validator.validate_metadata({
            "name": manifest.name,
            "description": manifest.description,
            "permissions": manifest.permissions,
        })
        if not report.is_valid:
            return False

        self._skills[manifest.name.lower()] = manifest
        return True

    def get_skill(self, name: str) -> Optional[SkillManifest]:
        return self._skills.get(name.lower().strip())

    def list_all_skills(self) -> List[SkillManifest]:
        return list(self._skills.values())

    def find_skills_by_trigger(self, trigger_phrase: str) -> List[SkillManifest]:
        query = trigger_phrase.lower().strip()
        matches = []
        for s in self._skills.values():
            if any(t.lower() in query for t in s.triggers):
                matches.append(s)
            elif query in s.description.lower():
                matches.append(s)
        return matches

    def unregister(self, name: str) -> bool:
        return self._skills.pop(name.lower().strip(), None) is not None
