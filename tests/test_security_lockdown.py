"""
tests.test_security_lockdown — Security Regression Tests for P0 Lockdown.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from actions.file_processor import file_processor
from core.self_modifier import self_edit_file, BASE_DIR
from dashboard.server import DashboardServer
from main import TOOL_DECLARATIONS
from mjx.security.permissions import (
    PermissionCategory,
    grant_permission,
    revoke_permission,
    emergency_stop,
    reset_emergency_stop,
)


def test_self_edit_removed_from_tool_declarations():
    """Verify self_edit and self_edit_file are not present in model tool declarations."""
    declared_names = [t["name"] for t in TOOL_DECLARATIONS if isinstance(t, dict) and "name" in t]
    assert "self_edit" not in declared_names
    assert "self_edit_file" not in declared_names


def test_self_edit_file_fails_closed_without_admin_permission():
    """Direct invocation of self_edit_file without ADMIN_OPERATION grant must fail closed."""
    revoke_permission(PermissionCategory.ADMIN_OPERATION)

    res = self_edit_file("main.py", "# injected content")
    assert "Security Error" in res
    assert "ADMIN_OPERATION" in res


def test_self_edit_file_blocks_path_traversal():
    """Attempting to modify a file outside the workspace must be rejected."""
    grant_permission(PermissionCategory.ADMIN_OPERATION, duration_seconds=10.0)

    try:
        res = self_edit_file("../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")
        assert "Safety Violation" in res
    finally:
        revoke_permission(PermissionCategory.ADMIN_OPERATION)


def test_dashboard_default_bind_localhost():
    """Dashboard must default to 127.0.0.1 and not expose 0.0.0.0."""
    server = DashboardServer()
    assert server.host == "127.0.0.1"
    url = server.get_url()
    assert "127.0.0.1" in url
    assert "0.0.0.0" not in url


def test_dashboard_unauthorized_endpoints_rejected():
    """Sensitive dashboard endpoints must reject unauthenticated requests with 401."""
    server = DashboardServer()
    client = TestClient(server.app)

    # 1. POST /api/command without auth
    resp1 = client.post("/api/command", json={"text": "open terminal"})
    assert resp1.status_code == 401

    # 2. GET /api/files without auth
    resp2 = client.get("/api/files")
    assert resp2.status_code == 401

    # 3. POST /api/upload without auth
    resp3 = client.post("/api/upload")
    assert resp3.status_code in (401, 422)  # 401 Unauthorized or 422 validation before auth

    # 4. POST /login with invalid PIN
    resp4 = client.post("/login", json={"pin": "WRONG_KEY"})
    assert resp4.status_code == 401


def test_file_processor_path_traversal_prevention(tmp_path):
    """File processor must detect and block path traversal and prohibited system files."""
    # Attempting to access /etc/passwd or shadow
    res1 = file_processor({"file_path": "/etc/passwd"})
    assert "Security Violation" in res1
    assert "Access denied" in res1

    # Attempting to access protected credentials inside workspace
    res2 = file_processor({"file_path": "config/.vault_recovery.key"})
    assert "Security Violation" in res2


def test_file_processor_permission_enforcement(tmp_path):
    """File processor must permit reads by default but enforce FILE_WRITE permission on writes."""
    test_file = tmp_path / "sample_doc.txt"
    test_file.write_text("Hello world testing content", encoding="utf-8")

    revoke_permission(PermissionCategory.FILE_WRITE)

    # 1. READ action: allowed under default policy (mock client error or success, but not Permission Denied)
    read_res = file_processor({"file_path": str(test_file), "action": "describe"})
    assert "Security Violation" not in read_res
    assert "Permission Denied" not in read_res

    # 2. WRITE action: without grant, must be blocked with Permission Denied
    write_res = file_processor({"file_path": str(test_file), "action": "convert"})
    assert "Permission Denied" in write_res
    assert "file_write" in write_res.lower()

    # 3. WRITE action with explicit grant: passes permission check
    grant_permission(PermissionCategory.FILE_WRITE, duration_seconds=10.0)
    try:
        granted_res = file_processor({"file_path": str(test_file), "action": "convert"})
        # Should proceed past permission check
        assert "Permission Denied" not in granted_res
    finally:
        revoke_permission(PermissionCategory.FILE_WRITE)


def test_emergency_stop_blocks_file_operations(tmp_path):
    """Engaging the Emergency Stop kill switch must block all file operations."""
    test_file = tmp_path / "safe.txt"
    test_file.write_text("Safe content", encoding="utf-8")

    emergency_stop()

    try:
        res = file_processor({"file_path": str(test_file), "action": "describe"})
        assert "Permission Denied" in res
    finally:
        reset_emergency_stop()
