"""
mjx.skills.skill_loader — Discovery and Parsing of SKILL.md Bundles.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SkillManifest:
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "custom"
    triggers: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    system_prompt: str = ""
    folder_path: Optional[str] = None


class SkillLoader:
    """Discovers and parses local skills with standard YAML frontmatter."""

    FRONTMATTER_REGEX = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

    def parse_skill_markdown(self, content: str, folder_path: Optional[str] = None) -> Optional[SkillManifest]:
        match = self.FRONTMATTER_REGEX.match(content.strip())
        if not match:
            return None

        frontmatter_text, body = match.groups()
        metadata: Dict[str, Any] = {}

        # Lightweight YAML key: value parser to avoid rigid external dependencies
        for line in frontmatter_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                k = key.strip()
                v = val.strip().strip("'\"")
                if v.startswith("[") and v.endswith("]"):
                    items = [i.strip().strip("'\"") for i in v[1:-1].split(",") if i.strip()]
                    metadata[k] = items
                else:
                    metadata[k] = v

        name = metadata.get("name")
        desc = metadata.get("description")
        if not name or not desc:
            return None

        triggers = metadata.get("triggers", [])
        if isinstance(triggers, str):
            triggers = [triggers]

        perms = metadata.get("permissions", [])
        if isinstance(perms, str):
            perms = [perms]

        return SkillManifest(
            name=str(name),
            description=str(desc),
            version=str(metadata.get("version", "1.0.0")),
            author=str(metadata.get("author", "unknown")),
            triggers=triggers,
            permissions=perms,
            system_prompt=body.strip(),
            folder_path=folder_path,
        )

    def load_from_directory(self, skill_dir: Path) -> Optional[SkillManifest]:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return None
        try:
            content = skill_file.read_text(encoding="utf-8")
            return self.parse_skill_markdown(content, folder_path=str(skill_dir))
        except Exception:
            return None
