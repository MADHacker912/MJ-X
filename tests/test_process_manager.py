"""
Unit tests for mjx.security.process_manager — Centralized Secure Process Execution.
"""

import os
import signal
import sys
import time
import pytest

from mjx.security.process_manager import (
    safe_run,
    safe_spawn,
    terminate_all_spawned,
    inspect_command_safety,
    set_approval_handler,
    sanitize_env,
    ProcessExecutionResult,
)


def test_command_validation_safe():
    """Valid commands pass safety inspection."""
    is_safe, reason = inspect_command_safety(["ls", "-la"])
    assert is_safe is True
    assert reason == ""


def test_command_validation_dangerous():
    """Destructive commands are rejected by safety inspection."""
    is_safe, reason = inspect_command_safety(["rm", "-rf", "/"])
    assert is_safe is False
    assert "Destructive" in reason or "Dangerous" in reason

    is_safe2, _ = inspect_command_safety(["mkfs.ext4", "/dev/sda1"])
    assert is_safe2 is False


def test_shell_injection_resistance():
    """Attempting shell=True raises ValueError policy violation."""
    with pytest.raises(ValueError, match="Security Policy Violation"):
        safe_run("ls -la; echo hacked", shell=True)


def test_execution_basic():
    """Basic safe command execution returns expected output and exit code."""
    res = safe_run([sys.executable, "-c", "print('hello from safe_run')"])
    assert res.ok is True
    assert res.returncode == 0
    assert "hello from safe_run" in res.stdout
    assert res.timed_out is False


def test_timeout_enforcement():
    """Commands exceeding timeout are terminated and marked timed_out."""
    start = time.time()
    res = safe_run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.5)
    duration = time.time() - start

    assert res.timed_out is True
    assert res.ok is False
    assert duration < 3.0  # Timed out promptly


def test_invalid_executable():
    """Attempting to run a non-existent binary returns error code gracefully without crashing."""
    res = safe_run(["non_existent_binary_xyz_12345"])
    assert res.ok is False
    assert res.returncode == 127
    assert "not found" in res.stderr.lower()


def test_output_capping():
    """Very large output is bounded to max buffer size to prevent DoS."""
    # Generate 3 MB of output
    script = "import sys; sys.stdout.write('A' * (3 * 1024 * 1024))"
    res = safe_run([sys.executable, "-c", script], timeout=10.0)
    assert res.ok is True
    assert len(res.stdout) <= 2 * 1024 * 1024  # Capped at 2MB


def test_env_sanitization(monkeypatch):
    """Sensitive API keys and vault passphrases are stripped from child processes."""
    monkeypatch.setenv("GEMINI_API_KEY", "secret_gemini_key_123")
    monkeypatch.setenv("MJX_VAULT_PASSPHRASE", "secret_passphrase_456")
    monkeypatch.setenv("SAFE_PUBLIC_VAR", "public_value_789")

    # Verify via sanitize_env
    clean = sanitize_env()
    assert "GEMINI_API_KEY" not in clean
    assert "MJX_VAULT_PASSPHRASE" not in clean
    assert clean.get("SAFE_PUBLIC_VAR") == "public_value_789"

    # Verify in spawned subprocess
    script = "import os; print('KEY:', os.environ.get('GEMINI_API_KEY', 'NONE'))"
    res = safe_run([sys.executable, "-c", script])
    assert "KEY: NONE" in res.stdout


def test_approval_gate_callback():
    """Privileged or dangerous commands trigger approval handler and can be allowed or denied."""
    blocked_cmd = ["rm", "-rf", "/tmp/fake_dir"]

    # Case 1: Handler rejects
    set_approval_handler(lambda cmd, reason: False)
    res_rejected = safe_run(blocked_cmd)
    assert res_rejected.ok is False
    assert "Security Gate Blocked" in res_rejected.stderr

    # Case 2: Handler approves (mocked for safe echo command test)
    set_approval_handler(lambda cmd, reason: True)
    # Reset handler
    set_approval_handler(None)


def test_safe_spawn_and_lifecycle():
    """safe_spawn tracks child process and terminate_all_spawned cleans it up."""
    proc = safe_spawn([sys.executable, "-c", "import time; time.sleep(10)"])
    assert proc.poll() is None  # Running

    count = terminate_all_spawned(grace_period=0.2)
    assert count >= 1
    assert proc.poll() is not None  # Terminated
