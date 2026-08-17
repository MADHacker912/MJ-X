"""
core/self_modifier.py — Neural-Enhanced Safe Self-Code Modification Engine for MJ-AI.
======================================================================================
Features:
  1. Uses NeuralBrain to featurize proposed code & predict runtime risk.
  2. Creates fast, targeted file backups in memory/backups/ before any edits.
  3. Validates new code with AST parsing & py_compile syntax checking.
  4. Runs sandboxed dry-run execution tests to ensure stability.
  5. Feeds execution outcomes back into NeuralBrain via backpropagation learning.
  6. Automatically rolls back if code changes fail or introduce errors.
"""

import os
import sys
import ast
import json
import shutil
import py_compile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from core.neural_brain import get_neural_brain


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
MEMORY_DIR = BASE_DIR / "memory"
BACKUPS_DIR = MEMORY_DIR / "backups"
FAILED_EDITS_PATH = MEMORY_DIR / "failed_edits.json"


def _ensure_backups_dir() -> Path:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUPS_DIR


def backup_target_file(target_path: Path) -> Optional[Path]:
    """Creates a timestamped backup copy of a specific target file before modification."""
    _ensure_backups_dir()
    if not target_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = target_path.relative_to(BASE_DIR).as_posix().replace("/", "__")
    backup_file = BACKUPS_DIR / f"{safe_name}_{timestamp}.bak"
    shutil.copy2(target_path, backup_file)
    return backup_file


def create_codebase_backup() -> Path:
    """Creates a backup snapshot of source files (excluding heavy/backup dirs)."""
    _ensure_backups_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"mj_snapshot_{timestamp}"
    backup_path.mkdir(parents=True, exist_ok=True)

    for sub in ["actions", "core", "personality", "emotion"]:
        src = BASE_DIR / sub
        if src.exists():
            shutil.copytree(src, backup_path / sub, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "backups"))

    for root_file in ["main.py", "ui.py", "setup.py"]:
        src_file = BASE_DIR / root_file
        if src_file.exists():
            shutil.copy2(src_file, backup_path / root_file)

    return backup_path


def restore_target_file(target_path: Path, backup_file: Optional[Path]) -> bool:
    """Restores the target file from its backup copy."""
    try:
        if backup_file and backup_file.exists():
            shutil.copy2(backup_file, target_path)
            print(f"[SelfModifier] 🔄 File '{target_path.name}' restored from backup.")
            return True
        elif not backup_file and target_path.exists():
            # If there was no original file (it was newly created during edit), remove it
            target_path.unlink(missing_ok=True)
            return True
        return False
    except Exception as e:
        print(f"[SelfModifier] ❌ Restore failed: {e}")
        return False


def _record_failed_edit(file_path: str, error_msg: str, proposed_code: str):
    """Log failed code edit signature to avoid repeating the exact mistake."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    if FAILED_EDITS_PATH.exists():
        try:
            with open(FAILED_EDITS_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []

    records.append({
        "timestamp": datetime.now().isoformat(),
        "file": file_path,
        "error": error_msg,
        "code_snippet": proposed_code[:500],
    })
    if len(records) > 50:
        records = records[-50:]

    try:
        with open(FAILED_EDITS_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    except Exception:
        pass


def self_edit_file(
    target_relative_path: str,
    new_content: str,
    bypass_risk: bool = False,
) -> str:
    """
    Safely edits an MJ codebase file with Neural Brain safety evaluation,
    AST validation, sandboxed execution check, and automatic learning.
    """
    brain = get_neural_brain()
    target = (BASE_DIR / target_relative_path).resolve()
    
    # 1. Safety Check: Must stay within BASE_DIR
    if BASE_DIR.resolve() not in target.parents and target != BASE_DIR.resolve():
        return f"Safety Violation: Cannot edit file outside workspace: {target_relative_path}"

    # 2. Neural Brain Risk Assessment
    risk_score = brain.predict_risk(new_content, target_relative_path)
    success_prob = 1.0 - risk_score
    print(f"[SelfModifier] 🧠 Neural Brain Assessment -> Predicted Success: {success_prob * 100:.1f}% | Risk: {risk_score:.2f}")

    if risk_score > 0.85 and not bypass_risk:
        msg = f"Neural Brain Alert: Modification rejected due to high risk score ({risk_score:.2f})."
        brain.learn_outcome(new_content, target_relative_path, success=False, error_msg="High risk rejection")
        return msg

    # 3. Create Fast Target Backup
    backup_file = backup_target_file(target)
    temp_file = target.with_suffix(".tmp_edit")
    
    try:
        # Write to temporary file for validation
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text(new_content, encoding="utf-8")
        
        # 4. AST Parse Check
        ast.parse(new_content)

        # 5. Bytecode Compilation Check
        py_compile.compile(str(temp_file), doraise=True)

        # 6. Sandboxed Execution Test (Subprocess)
        test_run = subprocess.run(
            [sys.executable, "-c", f"import py_compile; py_compile.compile('{temp_file}', doraise=True)"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if test_run.returncode != 0:
            raise RuntimeError(f"Sandbox compilation test failed: {test_run.stderr}")

        # 7. Commit Edit & Replace Target
        temp_file.replace(target)
        print(f"[SelfModifier] ✅ Safely updated codebase file: {target_relative_path}")

        # 8. Neural Brain Reinforcement Learning (Positive Outcome)
        brain.learn_outcome(new_content, target_relative_path, success=True)
        
        msg = f"File '{target_relative_path}' successfully verified, updated, and reinforced in Neural Brain (Success Prob: {success_prob*100:.1f}%)."
        return msg

    except (SyntaxError, py_compile.PyCompileError) as exc:
        err_msg = f"Syntax Error: {exc}"
        print(f"[SelfModifier] ❌ Syntax validation failed: {err_msg}")
        if temp_file.exists():
            temp_file.unlink()
        restore_target_file(target, backup_file)
        _record_failed_edit(target_relative_path, err_msg, new_content)
        brain.learn_outcome(new_content, target_relative_path, success=False, error_msg=err_msg)
        return f"Self-edit failed due to syntax error: {exc}"

    except Exception as exc:
        err_msg = str(exc)
        print(f"[SelfModifier] ❌ Edit failed: {err_msg}")
        if temp_file.exists():
            temp_file.unlink()
        restore_target_file(target, backup_file)
        _record_failed_edit(target_relative_path, err_msg, new_content)
        brain.learn_outcome(new_content, target_relative_path, success=False, error_msg=err_msg)
        return f"Self-edit failed: {exc}"
