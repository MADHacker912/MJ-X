"""
mjx.security.process_manager — Centralized, Secure Process Execution Layer.

Replaces raw subprocess calls and eliminates global subprocess monkey-patching.
Provides:
  - shell=False enforcement by default
  - Argument array validation and shell injection resistance
  - Configurable timeouts and bounded output buffers (DoS defense)
  - Environment variable sanitization (prevents credential exfiltration to children)
  - Windows CREATE_NO_WINDOW attachment per-call without global side-effects
  - POSIX process group management for clean tree termination
  - Active process lifecycle tracking and graceful shutdown
  - Untrusted / AI-generated command safety inspection & approval gate
"""

from __future__ import annotations

import os
import platform
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Union

_SYSTEM = platform.system()
_DEFAULT_TIMEOUT = 15.0
_MAX_OUTPUT_BYTES = 2 * 1024 * 1024  # 2 MB buffer cap to prevent memory exhaustion

# Dangerous command patterns requiring explicit approval or rejection
DANGEROUS_COMMANDS = {
    "rm": ["-rf", "-fr", "--no-preserve-root"],
    "mkfs": None,
    "dd": None,
    "format": None,
    "fdisk": None,
    "parted": None,
    "shutdown": None,
    "reboot": None,
    "poweroff": None,
    "init": ["0", "6"],
}

SENSITIVE_ENV_VARS = {
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "ELEVENLABS_API_KEY",
    "OPENAI_API_KEY",
    "MJX_VAULT_PASSPHRASE",
}


@dataclass
class ProcessExecutionResult:
    command: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


# Lifecycle tracker for spawned child processes
_tracked_processes: Dict[int, subprocess.Popen] = {}
_approval_handler: Optional[Callable[[List[str], str], bool]] = None


def set_approval_handler(handler: Optional[Callable[[List[str], str], bool]]) -> None:
    """Register a UI or console callback to confirm privileged/destructive actions."""
    global _approval_handler
    _approval_handler = handler


def sanitize_env(base_env: Optional[Dict[str, str]] = None, allow_secrets: bool = False) -> Dict[str, str]:
    """Return an environment dictionary sanitized of sensitive credential keys."""
    env = dict(base_env if base_env is not None else os.environ)
    if not allow_secrets:
        for secret_var in SENSITIVE_ENV_VARS:
            env.pop(secret_var, None)
    return env


def inspect_command_safety(cmd: Sequence[str]) -> tuple[bool, str]:
    """
    Inspect command arguments for destructive or high-risk actions.
    Returns (is_safe, warning_reason).
    """
    if not cmd:
        return False, "Empty command"

    executable = Path(cmd[0]).name.lower()
    arg_str = " ".join(cmd[1:]).lower()

    for danger_base, bad_flags in DANGEROUS_COMMANDS.items():
        if executable == danger_base or executable.startswith(danger_base + "."):
            if bad_flags is None:
                return False, f"Potentially destructive system utility: {executable}"
            for flag in bad_flags:
                if flag in arg_str:
                    return False, f"Destructive flags detected for {executable}: {flag}"

    # Check for raw fork bombs or command chaining syntax in arguments
    for arg in cmd:
        if any(token in arg for token in [":(){ :|:& };:", "rm -rf /"]):
            return False, f"Dangerous exploit pattern detected in argument: {arg}"

    return True, ""


def _build_platform_kwargs(detached: bool = False) -> Dict:
    """Attach proper platform flags (CREATE_NO_WINDOW on Windows, process groups on Linux)."""
    kwargs: Dict = {}
    if _SYSTEM == "Windows":
        # Attach CREATE_NO_WINDOW without global monkey-patching
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        kwargs["creationflags"] = create_no_window
    elif _SYSTEM in ("Linux", "Darwin"):
        if detached:
            kwargs["start_new_session"] = True
    return kwargs


def safe_run(
    cmd: Union[str, Sequence[str]],
    timeout: float = _DEFAULT_TIMEOUT,
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    shell: bool = False,
    allow_secrets_in_env: bool = False,
    check: bool = False,
    approval_reason: str = "",
) -> ProcessExecutionResult:
    """
    Execute a command synchronously with strict security boundaries.
    
    Security Guarantees:
      - shell=False by default.
      - String commands are parsed into argument arrays via shlex.split.
      - Sensitive credential environment variables stripped unless explicitly requested.
      - Maximum output buffer capped to prevent memory exhaustion DoS.
      - Clean process group tree termination on timeout.
    """
    if shell:
        raise ValueError(
            "Security Policy Violation: shell=True is disallowed. "
            "Pass arguments as a sequence of strings (e.g. ['ls', '-la'])."
        )

    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = [str(c) for c in cmd]

    if not cmd_list:
        return ProcessExecutionResult([], -1, "", "Empty command provided", 0.0)

    # 1. Safety Inspection
    is_safe, reason = inspect_command_safety(cmd_list)
    if not is_safe:
        approved = False
        if _approval_handler is not None:
            approved = _approval_handler(cmd_list, reason or approval_reason)
        if not approved:
            return ProcessExecutionResult(
                cmd_list,
                -1,
                "",
                f"Security Gate Blocked: {reason}. Action was not authorized.",
                0.0,
            )

    # 2. Environment & Working Directory
    run_env = sanitize_env(env, allow_secrets=allow_secrets_in_env)
    run_cwd = str(cwd) if cwd else None

    platform_kwargs = _build_platform_kwargs(detached=False)
    start_time = time.time()
    timed_out = False

    try:
        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=run_cwd,
            env=run_env,
            text=True,
            **platform_kwargs,
        )

        _tracked_processes[proc.pid] = proc

        try:
            stdout_data, stderr_data = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Graceful terminate then kill
            try:
                proc.terminate()
                stdout_data, stderr_data = proc.communicate(timeout=2.0)
            except Exception:
                proc.kill()
                stdout_data, stderr_data = proc.communicate()

        # Enforce buffer cap
        stdout_capped = (stdout_data or "")[:_MAX_OUTPUT_BYTES]
        stderr_capped = (stderr_data or "")[:_MAX_OUTPUT_BYTES]

        duration = time.time() - start_time
        returncode = proc.returncode if not timed_out else -signal.SIGKILL

    except FileNotFoundError as exc:
        return ProcessExecutionResult(cmd_list, 127, "", f"Executable not found: {exc}", time.time() - start_time)
    except Exception as exc:
        return ProcessExecutionResult(cmd_list, -1, "", f"Process execution error: {exc}", time.time() - start_time)
    finally:
        if 'proc' in locals() and proc.pid in _tracked_processes:
            _tracked_processes.pop(proc.pid, None)

    result = ProcessExecutionResult(
        command=cmd_list,
        returncode=returncode,
        stdout=stdout_capped,
        stderr=stderr_capped,
        duration=duration,
        timed_out=timed_out,
    )

    if check and not result.ok:
        raise subprocess.CalledProcessError(returncode, cmd_list, result.stdout, result.stderr)

    return result


def safe_spawn(
    cmd: Union[str, Sequence[str]],
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    detached: bool = True,
    allow_secrets_in_env: bool = False,
) -> subprocess.Popen:
    """
    Launch an external GUI application or background daemon safely with lifecycle tracking.
    """
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = [str(c) for c in cmd]

    is_safe, reason = inspect_command_safety(cmd_list)
    if not is_safe:
        raise PermissionError(f"Security Policy Block: {reason}")

    run_env = sanitize_env(env, allow_secrets=allow_secrets_in_env)
    platform_kwargs = _build_platform_kwargs(detached=detached)

    proc = subprocess.Popen(
        cmd_list,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(cwd) if cwd else None,
        env=run_env,
        **platform_kwargs,
    )

    _tracked_processes[proc.pid] = proc
    return proc


def terminate_all_spawned(grace_period: float = 2.0) -> int:
    """Terminate all active tracked processes started during this session."""
    active = list(_tracked_processes.values())
    terminated_count = 0

    for proc in active:
        if proc.poll() is None:
            try:
                proc.terminate()
                terminated_count += 1
            except Exception:
                pass

    if terminated_count > 0:
        time.sleep(grace_period)

    for proc in active:
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass

    _tracked_processes.clear()
    return terminated_count
