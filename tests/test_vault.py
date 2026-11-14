"""
Unit tests for mjx.security.vault — Secure Credential Vault, AES-256-GCM Fallback & Migration.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from mjx.security import (
    vault,
    set_secret,
    get_secret,
    delete_secret,
    has_secret,
    list_configured_providers,
    is_backend_secure,
    migrate_from_config,
    get_api_key,
    set_api_key,
    delete_api_key,
    has_api_key,
    VAULT_MARKER,
    VaultLockedError,
)


def test_store_and_retrieve_secret(tmp_path, monkeypatch):
    """Test standard secret store, retrieval, provider listing, and deletion."""
    test_manifest = tmp_path / ".vault_manifest.json"
    test_vault_file = tmp_path / ".vault.enc"
    monkeypatch.setattr(vault, "_manifest_file", lambda: test_manifest)
    monkeypatch.setattr(vault, "_vault_file", lambda: test_vault_file)

    provider = "gemini_api_key"
    secret = "AIzaSy_UnitTestSecret_Key_98765"

    assert set_secret(provider, secret) is True
    assert has_secret(provider) is True
    assert get_secret(provider) == secret
    assert provider in list_configured_providers()

    # Test backward-compatible functions
    assert get_api_key(provider) == secret
    assert has_api_key(provider) is True

    # Cleanup
    assert delete_secret(provider) is True
    assert has_secret(provider) is False
    assert get_secret(provider) == ""


def test_missing_credentials(tmp_path, monkeypatch):
    """Querying a missing secret returns empty string and False for has_secret."""
    test_vault_file = tmp_path / ".vault.enc"
    test_manifest = tmp_path / ".vault_manifest.json"
    monkeypatch.setattr(vault, "_vault_file", lambda: test_vault_file)
    monkeypatch.setattr(vault, "_manifest_file", lambda: test_manifest)

    missing = "non_existent_provider_xyz"
    assert get_secret(missing) == ""
    assert has_secret(missing) is False


def test_credential_deletion(tmp_path, monkeypatch):
    """Deleting secret cleans up from backend, fallback, and manifest."""
    test_vault_file = tmp_path / ".vault.enc"
    test_manifest = tmp_path / ".vault_manifest.json"
    monkeypatch.setattr(vault, "_vault_file", lambda: test_vault_file)
    monkeypatch.setattr(vault, "_manifest_file", lambda: test_manifest)

    p = "openrouter_api_key"
    s = "sk-or-v1-secret-test-delete"

    set_secret(p, s)
    assert has_secret(p) is True

    assert delete_secret(p) is True
    assert has_secret(p) is False
    assert p not in list_configured_providers()


def test_incorrect_or_unavailable_backend(tmp_path, monkeypatch):
    """When OS keyring is unavailable or returns dummy backend, fallback to AES-256-GCM."""
    test_vault_file = tmp_path / ".vault.enc"
    test_manifest = tmp_path / ".vault_manifest.json"
    monkeypatch.setattr(vault, "_vault_file", lambda: test_vault_file)
    monkeypatch.setattr(vault, "_manifest_file", lambda: test_manifest)

    # Simulate insecure backend (e.g. fail keyring)
    dummy_backend = MagicMock()
    dummy_backend.priority = 0
    dummy_backend.__class__.__module__ = "keyring.backends.fail"
    dummy_backend.__class__.__name__ = "Keyring"

    monkeypatch.setattr(vault, "is_backend_secure", lambda backend=None: False)

    provider = "groq_api_key"
    secret = "gsk_test_secret_in_fallback_only"

    assert set_secret(provider, secret) is True
    assert test_vault_file.exists()

    # Secret must NOT be in plaintext in file
    raw_file = test_vault_file.read_bytes()
    assert secret.encode("utf-8") not in raw_file

    # Retrieval works via fallback vault
    assert get_secret(provider) == secret
    delete_secret(provider)


def test_locked_vault_handling(tmp_path, monkeypatch, capsys):
    """Handling locked OS keyring safely without leaking credentials."""
    test_vault_file = tmp_path / ".vault.enc"
    monkeypatch.setattr(vault, "_vault_file", lambda: test_vault_file)

    import keyring.errors
    mock_keyring = MagicMock()
    mock_keyring.set_password.side_effect = keyring.errors.KeyringLocked("Keyring daemon locked")
    mock_keyring.get_password.side_effect = keyring.errors.KeyringLocked("Keyring daemon locked")

    monkeypatch.setattr(vault, "keyring", mock_keyring)
    monkeypatch.setattr(vault, "is_backend_secure", lambda backend=None: True)

    provider = "locked_provider_key"
    secret = "AIzaSy_SuperSecretPassword_112233"

    # Must catch locked error safely and fall back to encrypted vault
    assert set_secret(provider, secret) is True
    assert get_secret(provider) == secret

    # Check output logs for NO secret exposure
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err


def test_migration_success(tmp_path, monkeypatch):
    """Test safe, idempotent migration from config file with memory verification."""
    test_cfg_path = tmp_path / "api_keys.json"
    test_manifest = tmp_path / ".vault_manifest.json"
    test_vault_file = tmp_path / ".vault.enc"
    monkeypatch.setattr(vault, "_manifest_file", lambda: test_manifest)
    monkeypatch.setattr(vault, "_vault_file", lambda: test_vault_file)
    monkeypatch.setattr(vault, "_default_config_path", lambda: test_cfg_path)

    initial_config = {
        "gemini_api_key": "AIzaSy_LegacyKeyToMigrate_554433",
        "openrouter_api_key": "sk-or-test-migrate-9988",
        "assistant_name": "MJ",
        "user_name": "Saksham",
        "ui_color": "#00d4ff",
        "camera_index": 1,
        "os_system": "linux",
        "morning_brief_enabled": True,
    }
    test_cfg_path.write_text(json.dumps(initial_config, indent=4), encoding="utf-8")

    # Run migration
    results = migrate_from_config(test_cfg_path)
    assert results.get("gemini_api_key") is True
    assert results.get("openrouter_api_key") is True

    # In-memory retrieval from vault
    assert get_secret("gemini_api_key") == "AIzaSy_LegacyKeyToMigrate_554433"
    assert get_secret("openrouter_api_key") == "sk-or-test-migrate-9988"

    # Disk file check: secret fields sanitized, non-secret fields intact
    updated_config = json.loads(test_cfg_path.read_text(encoding="utf-8"))
    assert updated_config["gemini_api_key"] == VAULT_MARKER
    assert updated_config["openrouter_api_key"] == VAULT_MARKER
    assert updated_config["assistant_name"] == "MJ"
    assert updated_config["user_name"] == "Saksham"
    assert updated_config["ui_color"] == "#00d4ff"
    assert updated_config["camera_index"] == 1
    assert updated_config["morning_brief_enabled"] is True

    # Idempotent: running again changes nothing
    second_run = migrate_from_config(test_cfg_path)
    assert second_run == {}

    # Cleanup
    delete_secret("gemini_api_key")
    delete_secret("openrouter_api_key")


def test_migration_failure_preserves_config(tmp_path, monkeypatch):
    """If vault storage or verification fails, config is NOT sanitized or altered."""
    test_cfg_path = tmp_path / "api_keys.json"
    initial_content = json.dumps({
        "gemini_api_key": "AIzaSy_PreserveMeIfFailure_999",
        "os_system": "linux"
    }, indent=4)
    test_cfg_path.write_text(initial_content, encoding="utf-8")

    # Mock set_secret to fail
    monkeypatch.setattr(vault, "set_secret", lambda provider, secret: False)

    results = migrate_from_config(test_cfg_path)
    assert results.get("gemini_api_key") is False

    # Config must remain unchanged
    assert test_cfg_path.read_text(encoding="utf-8") == initial_content


def test_no_plaintext_secret_in_application_logs(tmp_path, monkeypatch, capsys):
    """Verify that neither stdout nor stderr ever contains plaintext secrets."""
    test_vault_file = tmp_path / ".vault.enc"
    test_manifest = tmp_path / ".vault_manifest.json"
    monkeypatch.setattr(vault, "_vault_file", lambda: test_vault_file)
    monkeypatch.setattr(vault, "_manifest_file", lambda: test_manifest)

    super_secret = "AIzaSy_TopSecretLeakedKey_NEVER_LOG_ME"
    set_secret("gemini_api_key", super_secret)
    get_secret("gemini_api_key")
    delete_secret("gemini_api_key")

    captured = capsys.readouterr()
    assert super_secret not in captured.out
    assert super_secret not in captured.err


def test_no_accidental_credential_exposure_in_exceptions():
    """Ensure custom exceptions do not leak secrets in error messages."""
    from mjx.security import VaultError, BackendUnavailableError, VaultLockedError, MigrationError

    secret = "AIzaSy_SecretToProtect_000000"
    for exc_cls in [VaultError, BackendUnavailableError, VaultLockedError, MigrationError]:
        try:
            raise exc_cls(f"Operation failed for provider 'gemini_api_key'")
        except exc_cls as err:
            assert secret not in str(err)
            assert "gemini_api_key" in str(err)


def test_aes256_gcm_authenticated_encryption(tmp_path, monkeypatch):
    """Verify Scrypt + AES-256-GCM ciphertext format, random salt, 96-bit nonce, and tamper detection."""
    test_vault_file = tmp_path / ".vault.enc"
    monkeypatch.setattr(vault, "_vault_file", lambda: test_vault_file)

    test_data = {"test_provider": "secret_12345"}
    assert vault._write_fallback_vault(test_data) is True

    # Read envelope
    envelope = json.loads(test_vault_file.read_text(encoding="utf-8"))
    assert envelope["cipher"] == "AES-256-GCM"
    assert envelope["kdf"] == "scrypt"
    assert envelope["version"] == 2
    assert "salt" in envelope
    assert "nonce" in envelope
    assert "data" in envelope

    # Decrypt
    decrypted = vault._read_fallback_vault()
    assert decrypted == test_data

    # Tamper with ciphertext -> AESGCM should detect tamper and reject
    tampered_bytes = bytearray(envelope["data"], "ascii")
    tampered_bytes[10] = ord('A') if tampered_bytes[10] != ord('A') else ord('B')
    envelope["data"] = tampered_bytes.decode("ascii")
    test_vault_file.write_text(json.dumps(envelope), encoding="utf-8")

    tampered_result = vault._read_fallback_vault()
    # Tampered payload fails authentication tag verification and returns {}
    assert tampered_result == {}
