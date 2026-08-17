"""
actions/slopwatch.py — SlopWatch AI Anti-Cheat & Reward Hacking Detector for MJ-AI.
===================================================================================
Detects and prevents LLM "reward hacking" shortcuts (disabling tests, suppressing
warnings, swallowing exceptions, arbitrary sleeps, and project file hacks).

Supports:
  1. Native .NET SlopWatch CLI (`slopwatch analyze`, `slopwatch init`)
  2. Built-in Multi-Language AST & Regex Slop Engine (Python, C#, JS/TS, Go, Rust)
"""

import os
import sys
import ast
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
DOTNET_TOOLS_DIR = Path.home() / ".dotnet" / "tools"
DOTNET_BIN = Path.home() / ".dotnet" / "dotnet"


def _find_slopwatch_binary() -> Optional[str]:
    """Finds the slopwatch binary in PATH or ~/.dotnet/tools."""
    found = shutil.which("slopwatch")
    if found:
        return found
    custom_path = DOTNET_TOOLS_DIR / "slopwatch"
    if custom_path.exists() and os.access(custom_path, os.X_OK):
        return str(custom_path)
    return None


# ── Built-in Multi-Language Slop Rules ───────────────────────────────────────
SLOP_RULES = [
    {
        "code": "SW001",
        "severity": "ERROR",
        "name": "Disabled Tests",
        "desc": "Skipped or commented-out test cases to cheat test passes.",
        "patterns": [
            r'\[(?:Fact|Theory|Test)\s*\(\s*(?:Skip|Ignore)\s*=',
            r'\[Ignore(?:Attribute)?(?:\([^)]*\))?\]',
            r'@pytest\.mark\.skip',
            r'@unittest\.skip',
            r'\b(?:xit|it\.skip|describe\.skip|test\.skip)\s*\(',
        ]
    },
    {
        "code": "SW002",
        "severity": "WARNING",
        "name": "Warning Suppression",
        "desc": "Suppressing compiler or linter diagnostics instead of fixing issues.",
        "patterns": [
            r'#pragma\s+warning\s+disable',
            r'\[SuppressMessage\s*\(',
            r'#\s*noqa\b',
            r'#\s*type:\s*ignore',
            r'//\s*eslint-disable',
            r'@pytest\.mark\.filterwarnings\s*\(\s*["\']ignore',
        ]
    },
    {
        "code": "SW003",
        "severity": "ERROR",
        "name": "Swallowed Exception",
        "desc": "Empty catch or except blocks hiding bugs and errors.",
        "patterns": [
            r'catch\s*\([^)]*\)\s*\{\s*\}',
            r'except\s*(?:Exception)?\s*:\s*(?:pass|\.\.\.)',
            r'catch\s*\{\s*\}',
        ]
    },
    {
        "code": "SW004",
        "severity": "WARNING",
        "name": "Arbitrary Delay / Race Masking",
        "desc": "Adding arbitrary sleeps or timeouts to mask timing/race issues.",
        "patterns": [
            r'Task\.Delay\s*\(\s*\d{3,}\s*\)',
            r'Thread\.Sleep\s*\(\s*\d{3,}\s*\)',
            r'time\.sleep\s*\(\s*(?:[1-9]|\d+\.\d+)\s*\)',
            r'setTimeout\s*\([^,]+,\s*[1-9]\d{3,}\)',
        ]
    },
    {
        "code": "SW005",
        "severity": "WARNING",
        "name": "Project Warning Bypass",
        "desc": "Suppressing warnings or turning off TreatWarningsAsErrors in project configs.",
        "patterns": [
            r'<NoWarn>.*?</NoWarn>',
            r'<TreatWarningsAsErrors>false</TreatWarningsAsErrors>',
        ]
    },
    {
        "code": "SW006",
        "severity": "ERROR",
        "name": "Central Package Mgmt Bypass",
        "desc": "Bypassing CPM via VersionOverride or inline Version attributes.",
        "patterns": [
            r'<PackageReference\b[^>]*\bVersionOverride=',
        ]
    }
]


def scan_file_for_slop(file_path: Path) -> List[Dict[str, Any]]:
    """Scans a single file for slop / reward hacking patterns."""
    findings = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        for line_idx, line in enumerate(lines, 1):
            for rule in SLOP_RULES:
                for pat in rule["patterns"]:
                    if re.search(pat, line, re.IGNORECASE):
                        findings.append({
                            "line": line_idx,
                            "rule": rule["code"],
                            "severity": rule["severity"],
                            "name": rule["name"],
                            "desc": rule["desc"],
                            "snippet": line.strip()[:100]
                        })
                        break
    except Exception:
        pass
    return findings


def slopwatch_scan(target_path_str: str = "", use_native_cli: bool = True) -> str:
    """
    Runs SlopWatch anti-cheat inspection on target file or directory.
    Uses native SlopWatch .NET CLI if available, with built-in multi-language engine.
    """
    target = (BASE_DIR / target_path_str).resolve() if target_path_str else BASE_DIR

    # Check if native CLI is available
    cli_bin = _find_slopwatch_binary() if use_native_cli else None

    if cli_bin and target.is_dir() and (any(target.glob("*.sln")) or any(target.glob("*.csproj"))):
        try:
            env = os.environ.copy()
            dotnet_dir = Path.home() / ".dotnet"
            env["DOTNET_ROOT"] = str(dotnet_dir)
            env["PATH"] = f"{dotnet_dir}:{dotnet_dir / 'tools'}:{env.get('PATH', '')}"
            res = subprocess.run(
                [cli_bin, "analyze", "-d", str(target), "--no-baseline"],
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            if res.stdout.strip():
                return f"🛡️ SLOPWATCH .NET SCAN REPORT:\n{res.stdout.strip()}"
        except Exception:
            pass

    # Built-in multi-language engine
    if target.is_file():
        files_to_scan = [target]
    else:
        files_to_scan = [
            p for p in target.rglob("*")
            if p.is_file() and p.suffix.lower() in (
                ".cs", ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".csproj", ".props"
            ) and not any(part.startswith((".", "__pycache__", ".venv", "node_modules", "bin", "obj")) for part in p.parts)
        ]

    all_findings = []
    for f in files_to_scan:
        file_findings = scan_file_for_slop(f)
        for item in file_findings:
            try:
                rel = str(f.relative_to(BASE_DIR))
            except ValueError:
                rel = str(f)
            all_findings.append({"file": rel, **item})

    report = [
        "🛡️ SLOPWATCH ANTI-CHEAT AUDIT REPORT",
        "=" * 55,
        f"Scanned {len(files_to_scan)} files in: {target_path_str or 'MJ Workspace'}",
        "=" * 55,
    ]

    if not all_findings:
        report.append("✅ Zero AI reward hacking / slop patterns detected! Code is clean & honest.")
    else:
        report.append(f"⚠️ Found {len(all_findings)} AI Reward-Hacking / Slop Issue(s):\n")
        for i, item in enumerate(all_findings, 1):
            sev_icon = "❌" if item["severity"] == "ERROR" else "⚠️"
            report.append(f"[{i}] {sev_icon} [{item['rule']}] {item['file']}:{item['line']} -> {item['name']}")
            report.append(f"    Issue   : {item['desc']}")
            report.append(f"    Snippet : {item['snippet']}\n")

    return "\n".join(report)


def slopwatch_action(parameters: dict, player=None, speak=None) -> str:
    """Dispatcher for the slopwatch skill."""
    action = str(parameters.get("action", "scan")).lower().strip()
    target = str(parameters.get("target", "") or parameters.get("path", "")).strip()

    if action in ("scan", "analyze", "audit"):
        res = slopwatch_scan(target)
        if player and hasattr(player, "show_content"):
            player.show_content("SLOPWATCH REPORT", res)
        return res

    return slopwatch_scan(target)
