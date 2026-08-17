"""
actions/ponytail.py — Senior Dev "Lazy / Minimalist" Engineering Skill for MJ-AI.
================================================================================
Channels a veteran senior engineer: forces the laziest solution that actually works,
eliminates bloat, reaches for Python stdlib before packages, and deletes over-engineered code.

Supports intensity modes:
  - 'lite' : Names the minimal/stdlib alternative.
  - 'full' : Enforces the ladder (stdlib first, shortest working diff). [Default]
  - 'ultra': Extreme YAGNI. Deletes boilerplate, ships 1-liners.
"""

import os
import sys
import ast
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PONYTAIL_CONFIG_PATH = BASE_DIR / "memory" / "ponytail_config.json"


def _get_api_key() -> Optional[str]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("gemini_api_key")
    except Exception:
        return None


def get_ponytail_intensity() -> str:
    """Returns current ponytail intensity level: lite, full, or ultra."""
    if PONYTAIL_CONFIG_PATH.exists():
        try:
            with open(PONYTAIL_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("intensity", "full")
        except Exception:
            pass
    return "full"


def set_ponytail_intensity(level: str) -> str:
    """Sets ponytail intensity level: lite, full, or ultra."""
    level = level.lower().strip()
    if level not in ("lite", "full", "ultra"):
        level = "full"
    PONYTAIL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PONYTAIL_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"intensity": level}, f, indent=2)
    return f"Ponytail intensity set to '{level}'."


def _analyze_code_for_bloat(file_path: Path) -> List[Dict[str, Any]]:
    """Analyzes a Python file for common over-engineering and bloat patterns."""
    findings = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
        lines = content.splitlines()

        # Check 1: Factory / Single Implementation Abstract Classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if any("Factory" in node.name or "Manager" in node.name or "Provider" in node.name for _ in [1]):
                    if len(node.body) <= 2:
                        findings.append({
                            "line": node.lineno,
                            "type": "Speculative Abstraction",
                            "msg": f"Class '{node.name}' looks like single-use boilerplate/factory.",
                            "fix": "Replace with a simple function or direct instantiation."
                        })

        # Check 2: Reinvented Stdlib / Redundant Imports
        redundant_pkgs = {
            "requests": "urllib.request (if simple GET/POST)",
            "pytz": "zoneinfo (Python 3.9+ stdlib)",
            "mock": "unittest.mock (stdlib)",
            "simplejson": "json (stdlib)",
            "termcolor": "native ANSI escape codes",
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod_name = getattr(node, "module", "") or ""
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in redundant_pkgs:
                            findings.append({
                                "line": node.lineno,
                                "type": "Redundant Dependency",
                                "msg": f"Imported '{alias.name}'.",
                                "fix": f"Use stdlib '{redundant_pkgs[alias.name]}' instead."
                            })

        # Check 3: Complex hand-rolled cache
        if "class" in content and "cache" in content.lower() and "def get" in content and "def set" in content:
            findings.append({
                "line": 1,
                "type": "Reinvented Cache",
                "msg": "Hand-rolled cache class detected.",
                "fix": "Use '@functools.lru_cache' or 'functools.cache' from stdlib."
            })

    except Exception as e:
        pass

    return findings


def ponytail_audit(target_path_str: str = "") -> str:
    """
    Performs a codebase audit hunting exclusively for over-engineering, bloat,
    reinvented standard libraries, and dead abstractions.
    """
    target = (BASE_DIR / target_path_str).resolve() if target_path_str else BASE_DIR

    if target.is_file():
        py_files = [target] if target.suffix == ".py" else []
    else:
        py_files = [
            p for p in target.rglob("*.py")
            if not any(part.startswith((".", "__pycache__", ".venv", "env", "site-packages")) for part in p.parts)
        ]

    total_files = len(py_files)
    all_findings = []

    for f in py_files:
        findings = _analyze_code_for_bloat(f)
        for item in findings:
            all_findings.append({
                "file": str(f.relative_to(BASE_DIR)),
                **item
            })

    report = [
        "🧹 PONYTAIL OVER-ENGINEERING AUDIT REPORT",
        "=" * 55,
        f"Scanned {total_files} Python files in: {target_path_str or 'MJ Workspace'}",
        f"Intensity Mode: {get_ponytail_intensity().upper()}",
        "=" * 55,
    ]

    if not all_findings:
        report.append("✅ Clean codebase! No speculative abstractions or reinvented stdlib detected.")
    else:
        report.append(f"Found {len(all_findings)} simplification opportunities:\n")
        for i, item in enumerate(all_findings, 1):
            report.append(f"[{i}] {item['file']}:{item['line']} -> {item['type']}")
            report.append(f"    Issue : {item['msg']}")
            report.append(f"    Action: {item['fix']}\n")

    return "\n".join(report)


def ponytail_review(code_or_file: str) -> str:
    """
    Reviews code from a Senior Minimalist Developer perspective.
    Tells you what to delete, what stdlib replaces it, and how to write the 1-line solution.
    """
    api_key = _get_api_key()
    if not api_key:
        return "Ponytail review requires gemini_api_key in config/api_keys.json."

    # If code_or_file points to an existing file path, read it
    file_path = BASE_DIR / code_or_file.strip()
    if file_path.exists() and file_path.is_file():
        code_content = file_path.read_text(encoding="utf-8", errors="ignore")
        source_label = f"File: {code_or_file}"
    else:
        code_content = code_or_file
        source_label = "Provided Code Snippet"

    intensity = get_ponytail_intensity()

    prompt = f"""You are Ponytail — an experienced, minimalist Senior Developer.
Your core philosophy: "The best code is the code never written. Deletion over addition. Stdlib first."

Intensity: {intensity.upper()}

Review this code and give the simplest, shortest, most lazy-yet-bulletproof solution:
1. Identify unneeded abstractions, boilerplate, or external dependencies that Python's stdlib already does in 1-2 lines.
2. Provide the ultra-minimal refactored code.
3. End with at most 2 bullet points: what was deleted, and why.

Source: {source_label}
```python
{code_content[:4000]}
```"""

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        return resp.text.strip()
    except Exception as e:
        return f"Ponytail review failed: {e}"


def ponytail_action(parameters: dict, player=None, speak=None) -> str:
    """Dispatcher for the ponytail skill."""
    action = str(parameters.get("action", "review")).lower().strip()
    target = str(parameters.get("target", "") or parameters.get("code", "")).strip()
    level  = str(parameters.get("level", "")).lower().strip()

    if action == "set_mode" or (level in ("lite", "full", "ultra") and not target):
        return set_ponytail_intensity(level or "full")

    if action == "audit":
        res = ponytail_audit(target)
        if player and hasattr(player, "show_content"):
            player.show_content("PONYTAIL AUDIT", res)
        return res

    if action in ("review", "simplify", "fix"):
        res = ponytail_review(target)
        if player and hasattr(player, "show_content"):
            player.show_content("PONYTAIL MINIMAL REVIEW", res)
        return res

    if action == "help":
        return (
            "Ponytail Skill Commands:\n"
            "- ponytail action='audit' target='actions/' -> Scans for bloat and over-engineering.\n"
            "- ponytail action='review' target='main.py' -> Senior dev simplification review.\n"
            "- ponytail action='set_mode' level='ultra|full|lite' -> Set intensity level."
        )

    return ponytail_review(target or "def example(): pass")
