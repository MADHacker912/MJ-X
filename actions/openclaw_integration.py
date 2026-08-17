"""
actions/openclaw_integration.py — Integration between MJ-AI and OpenClaw agent execution engine.
"""

import subprocess
import json
import shutil
import os
from pathlib import Path

OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
OPENCLAW_WORKSPACE = Path.home() / ".openclaw" / "workspace"

def _get_openclaw_bin() -> str:
    claw_bin = shutil.which("openclaw")
    if claw_bin:
        return claw_bin
    # Common locations if not in PATH
    nvm_bin = Path.home() / ".nvm" / "versions" / "node"
    if nvm_bin.exists():
        for p in nvm_bin.glob("*/bin/openclaw"):
            if p.exists():
                return str(p)
    usr_local = Path("/usr/local/bin/openclaw")
    if usr_local.exists():
        return str(usr_local)
    return "openclaw"

def openclaw_task(
    parameters: dict,
    player=None,
    speak=None,
) -> str:
    """
    Executes tasks using OpenClaw agent CLI or gateway API.
    parameters:
      - task / description / query: string describing what code/task to generate/run
      - action: 'run' | 'status' | 'agent'
      - workspace: optional path
    """
    p = parameters or {}
    task_desc = p.get("task") or p.get("description") or p.get("query") or ""
    action = p.get("action", "run").lower().strip()
    
    if not task_desc and action == "run":
        return "Please specify a task or description for OpenClaw to execute, sir."

    openclaw_cmd = _get_openclaw_bin()

    if player:
        player.write_log(f"[OpenClaw] Executing action '{action}' for task: {task_desc[:50]}...")

    if speak:
        speak(f"Delegating task to OpenClaw agent engine.")

    try:
        if action == "status":
            res = subprocess.run(
                [openclaw_cmd, "--version"],
                capture_output=True, text=True, timeout=10
            )
            if res.returncode == 0:
                return f"OpenClaw status: Active ({res.stdout.strip()})"
            return f"OpenClaw check failed: {res.stderr.strip()}"

        workspace_dir = p.get("workspace") or str(OPENCLAW_WORKSPACE)
        os.makedirs(workspace_dir, exist_ok=True)

        cmd = [openclaw_cmd, "run", task_desc]
        
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=workspace_dir,
            timeout=120
        )

        output = res.stdout.strip()
        err = res.stderr.strip()

        if res.returncode == 0:
            result_msg = f"OpenClaw task completed successfully.\n\nOutput:\n{output or 'Done'}"
            if player:
                player.write_log("[OpenClaw] Task succeeded.")
            return result_msg
        else:
            cmd_alt = [openclaw_cmd, "agent", "--prompt", task_desc]
            res_alt = subprocess.run(
                cmd_alt,
                capture_output=True,
                text=True,
                cwd=workspace_dir,
                timeout=120
            )
            if res_alt.returncode == 0:
                return f"OpenClaw agent task finished.\n\nOutput:\n{res_alt.stdout.strip()}"

            return f"OpenClaw execution failed:\n{err or res.stdout.strip() or 'Unknown error'}"

    except subprocess.TimeoutExpired:
        return "OpenClaw task timed out after 120 seconds."
    except FileNotFoundError:
        return f"OpenClaw CLI binary ('{openclaw_cmd}') was not found. Make sure OpenClaw is installed."
    except Exception as e:
        return f"OpenClaw error: {e}"
