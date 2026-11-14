"""
Unit tests for mjx.security.permissions — Permission and Safety System.
"""

import time
from pathlib import Path
import pytest

from mjx.security.permissions import (
    PermissionCategory,
    PermissionManager,
)


@pytest.fixture
def manager(tmp_path):
    return PermissionManager(log_dir=tmp_path / "logs")


def test_least_privilege_defaults(manager):
    """Read-only and app launches allowed; sensitive actions denied by default."""
    assert manager.check(PermissionCategory.READ_ONLY, "read_status") is True
    assert manager.check(PermissionCategory.FILE_READ, "read_readme", target="README.md") is True

    # Sensitive categories denied without explicit grant
    assert manager.check(PermissionCategory.SCREEN_CAPTURE, "capture_screen") is False
    assert manager.check(PermissionCategory.CAMERA_ACCESS, "capture_webcam") is False
    assert manager.check(PermissionCategory.FILE_WRITE, "write_config", target="test.txt") is False
    assert manager.check(PermissionCategory.OS_INPUT_CONTROL, "mouse_click") is False
    assert manager.check(PermissionCategory.ADMIN_OPERATION, "reboot_machine") is False


def test_grant_and_scoped_check(manager):
    """Scoped permission grants allow targeted actions."""
    manager.grant(PermissionCategory.FILE_WRITE, scope="/home/user/safe_dir")

    # Target matching scope is permitted
    assert manager.check(PermissionCategory.FILE_WRITE, "write_file", target="/home/user/safe_dir/output.txt") is True

    # Target outside scope is denied
    assert manager.check(PermissionCategory.FILE_WRITE, "write_file", target="/etc/passwd") is False


def test_permission_expiration(manager):
    """Time-bounded grants expire automatically."""
    manager.grant(PermissionCategory.SCREEN_CAPTURE, duration_seconds=0.1)
    assert manager.check(PermissionCategory.SCREEN_CAPTURE, "take_shot") is True

    time.sleep(0.15)
    assert manager.check(PermissionCategory.SCREEN_CAPTURE, "take_shot") is False


def test_one_time_grant(manager):
    """One-time grants are consumed after single use."""
    manager.grant(PermissionCategory.CAMERA_ACCESS, one_time=True)
    assert manager.check(PermissionCategory.CAMERA_ACCESS, "snap_photo") is True

    # Second check must fail
    assert manager.check(PermissionCategory.CAMERA_ACCESS, "snap_photo") is False


def test_revocation(manager):
    """Revoking permission immediately blocks previously granted actions."""
    manager.grant(PermissionCategory.OS_INPUT_CONTROL, scope="*")
    assert manager.check(PermissionCategory.OS_INPUT_CONTROL, "key_press") is True

    revoked = manager.revoke(PermissionCategory.OS_INPUT_CONTROL)
    assert revoked == 1
    assert manager.check(PermissionCategory.OS_INPUT_CONTROL, "key_press") is False


def test_emergency_stop(manager):
    """Emergency stop kill-switch blocks ALL actions, even previously granted ones."""
    manager.grant(PermissionCategory.SCREEN_CAPTURE)
    assert manager.check(PermissionCategory.SCREEN_CAPTURE, "shot") is True

    manager.emergency_stop()
    assert manager.is_emergency_stopped is True

    # Even read-only is blocked during emergency stop
    assert manager.check(PermissionCategory.READ_ONLY, "any_action") is False
    assert manager.check(PermissionCategory.SCREEN_CAPTURE, "shot") is False

    manager.reset_emergency_stop()
    assert manager.is_emergency_stopped is False
    assert manager.check(PermissionCategory.SCREEN_CAPTURE, "shot") is True


def test_user_prompt_callback(manager):
    """Unapproved sensitive actions invoke prompt callback."""
    # Callback approves screen capture but denies admin operation
    def mock_ui_prompt(category, action, target, reason):
        return category == PermissionCategory.SCREEN_CAPTURE

    manager.set_prompt_callback(mock_ui_prompt)

    assert manager.check(PermissionCategory.SCREEN_CAPTURE, "take_shot") is True
    assert manager.check(PermissionCategory.ADMIN_OPERATION, "format_drive") is False


def test_audit_logging(manager):
    """Audit records are created for all permission checks without credentials."""
    manager.check(PermissionCategory.READ_ONLY, "audit_test_action", target="test_target")
    records = manager.get_audit_records(limit=10)

    assert len(records) >= 1
    last = records[0]
    assert last["action"] == "audit_test_action"
    assert last["decision"] == "ALLOWED"
    assert "timestamp" in last
    assert "iso_time" in last
