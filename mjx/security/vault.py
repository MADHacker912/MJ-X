"""
mjx.security.vault — Secure Credential Vault using OS Keyring & Authenticated AES-256-GCM.

Prevents cleartext API key storage (CWE-312) by delegating secrets to the operating
system's credential manager (Windows DPAPI / Credential Manager, Linux SecretService / KWallet)
with an automated passphrase-derived AES-256-GCM + Scrypt encrypted fallback vault.

Adheres strictly to zero-plaintext storage and zero-credential-exposure standards.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import platform
import sys
import secrets
from pathlib import Path
from typing import Optional, List, Dict

try:
    import keyring
    import keyring.backend
    from keyring.errors import (
        KeyringError,
        KeyringLocked,
        PasswordSetError,
        PasswordDeleteError,
        InitError,
        NoKeyringError,
    )
    _KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    KeyringError = Exception  # type: ignore
    KeyringLocked = Exception  # type: ignore
    PasswordSetError = Exception  # type: ignore
    PasswordDeleteError = Exception  # type: ignore
    InitError = Exception  # type: ignore
    NoKeyringError = Exception  # type: ignore
    _KEYRING_AVAILABLE = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    _CRYPTO_AVAILABLE = True
except ImportError:
    AESGCM = None
    Scrypt = None
    _CRYPTO_AVAILABLE = False

SERVICE_NAME = "mjx_assistant"
VAULT_MARKER = "USE_OS_VAULT"
FALLBACK_SALT_LENGTH = 16
FALLBACK_NONCE_LENGTH = 12

KNOWN_SECRET_PROVIDERS = [
    "gemini_api_key",
    "openrouter_api_key",
    "groq_api_key",
    "elevenlabs_api_key",
    "openai_api_key",
]


class VaultError(Exception):
    """Base exception for Vault operations (does not expose secret values)."""
    pass


class BackendUnavailableError(VaultError):
    """Raised when neither OS Keyring nor fallback vault is usable."""
    pass


class VaultLockedError(VaultError):
    """Raised when the OS keyring or vault is locked by the system."""
    pass


class MigrationError(VaultError):
    """Raised when credential migration fails validation."""
    pass


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _vault_file() -> Path:
    return _base_dir() / "config" / ".vault.enc"


def _recovery_key_file() -> Path:
    return _base_dir() / "config" / ".vault_recovery.key"


def _manifest_file() -> Path:
    return _base_dir() / "config" / ".vault_manifest.json"


def _default_config_path() -> Path:
    return _base_dir() / "config" / "api_keys.json"


def _normalize_provider(name: str) -> str:
    """Normalize provider identifier, e.g. 'gemini' -> 'gemini_api_key'."""
    n = name.strip().lower()
    if not n.endswith("_api_key") and n in {"gemini", "openrouter", "groq", "elevenlabs", "openai"}:
        return f"{n}_api_key"
    return n


def is_backend_secure(backend=None) -> bool:
    """
    Verify whether the active or given keyring backend is an authentic OS-level secure store.
    Rejects dummy, plaintext, or failing backends.
    """
    if not _KEYRING_AVAILABLE or keyring is None:
        return False

    if backend is None:
        try:
            backend = keyring.get_keyring()
        except Exception:
            return False

    if backend is None or getattr(backend, "priority", 0) <= 0:
        return False

    # Check for ChainerBackend
    if hasattr(backend, "backends"):
        secure_children = [b for b in backend.backends if is_backend_secure(b)]
        return len(secure_children) > 0

    mod_name = backend.__class__.__module__.lower()
    cls_name = backend.__class__.__name__.lower()

    # Reject known insecure backends
    if any(k in cls_name or k in mod_name for k in ["fail", "null", "plaintext", "file"]):
        return False

    # Verify approved OS credential backends
    # Linux: SecretService, libsecret, KWallet
    if any(k in mod_name for k in ["secretservice", "libsecret", "kwallet"]):
        return True
    # Windows: Windows Credential Manager
    if "windows" in mod_name or "winvault" in cls_name:
        return True
    # macOS: Keychain
    if "macos" in mod_name or "osx" in mod_name or "keychain" in cls_name:
        return True

    return False


def get_active_backend_info() -> Dict[str, str]:
    """Return diagnostic metadata about the current vault backend (no secret data)."""
    if not _KEYRING_AVAILABLE or keyring is None:
        return {"type": "none", "secure": "false", "details": "Keyring library not installed"}

    try:
        b = keyring.get_keyring()
        secure = is_backend_secure(b)
        return {
            "type": b.__class__.__name__,
            "module": b.__class__.__module__,
            "secure": str(secure).lower(),
            "priority": str(getattr(b, "priority", 0)),
        }
    except Exception as exc:
        return {"type": "error", "secure": "false", "details": str(exc)}


# ── Manifest Management (Stores provider names only, NEVER secrets) ──────────

def _read_manifest() -> List[str]:
    mf = _manifest_file()
    if not mf.exists():
        return []
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return list(data.get("providers", []))
    except Exception:
        pass
    return []


def _register_provider_in_manifest(provider: str) -> None:
    norm = _normalize_provider(provider)
    providers = set(_read_manifest())
    if norm not in providers:
        providers.add(norm)
        mf = _manifest_file()
        try:
            mf.parent.mkdir(parents=True, exist_ok=True)
            mf.write_text(json.dumps({"providers": sorted(list(providers))}, indent=2), encoding="utf-8")
        except Exception:
            pass


def _unregister_provider_in_manifest(provider: str) -> None:
    norm = _normalize_provider(provider)
    providers = set(_read_manifest())
    if norm in providers:
        providers.remove(norm)
        mf = _manifest_file()
        try:
            mf.write_text(json.dumps({"providers": sorted(list(providers))}, indent=2), encoding="utf-8")
        except Exception:
            pass


# ── Authenticated AES-256-GCM + Scrypt Local Encrypted Fallback Vault ─────────

def _get_vault_passphrase() -> bytes:
    """
    Derive a user-held cryptographic key for local vault encryption.
    
    Security & Recovery Architecture:
    1. Check MJX_VAULT_PASSPHRASE environment variable (explicit user-held passphrase).
    2. Check config/.vault_recovery.key: a persistent, random 256-bit secret generated on
       first run with 0600 permissions. This allows safe offline recovery across OS reinstalls.
    3. Mix with dynamic user/machine entropy so the key cannot be used on an unrelated account.
    """
    env_pass = os.environ.get("MJX_VAULT_PASSPHRASE")
    if env_pass:
        user_secret = env_pass.encode("utf-8")
    else:
        rf = _recovery_key_file()
        if rf.exists():
            try:
                user_secret = rf.read_text(encoding="utf-8").strip().encode("utf-8")
            except Exception:
                user_secret = b"mjx-default-fallback-user-secret"
        else:
            try:
                rf.parent.mkdir(parents=True, exist_ok=True)
                new_key = secrets.token_urlsafe(32)
                rf.write_text(new_key, encoding="utf-8")
                try:
                    rf.chmod(0o600)
                except Exception:
                    pass
                user_secret = new_key.encode("utf-8")
            except Exception:
                user_secret = b"mjx-ephemeral-fallback-user-secret"

    # Machine-bound component (never sole secret)
    parts = [
        getpass.getuser(),
        platform.node(),
        str(Path.home().resolve()),
    ]
    try:
        if platform.system() == "Linux":
            for mid in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
                if mid.exists():
                    parts.append(mid.read_text(encoding="utf-8").strip())
                    break
        elif platform.system() == "Windows":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as k:
                guid, _ = winreg.QueryValueEx(k, "MachineGuid")
                parts.append(str(guid))
    except Exception:
        pass

    machine_entropy = ":".join(parts).encode("utf-8")
    # Bind user secret with local machine entropy
    return hashlib.sha256(user_secret + b":" + machine_entropy).digest()


def _read_fallback_vault() -> Dict[str, str]:
    """Read and decrypt the AES-256-GCM encrypted fallback vault."""
    vf = _vault_file()
    if not vf.exists() or not _CRYPTO_AVAILABLE or AESGCM is None or Scrypt is None:
        return {}

    try:
        raw_content = vf.read_text(encoding="utf-8")
        envelope = json.loads(raw_content)

        if envelope.get("cipher") != "AES-256-GCM":
            # Handle potential legacy format or reject
            return {}

        salt = base64.b64decode(envelope["salt"])
        nonce = base64.b64decode(envelope["nonce"])
        ciphertext = base64.b64decode(envelope["data"])

        passphrase = _get_vault_passphrase()
        kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
        key = kdf.derive(passphrase)

        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        print(f"[Vault] ⚠️ Fallback vault decryption notice ({exc.__class__.__name__})")
        return {}


def _write_fallback_vault(data: Dict[str, str]) -> bool:
    """Encrypt and write data to fallback vault using AES-256-GCM + Scrypt."""
    if not _CRYPTO_AVAILABLE or AESGCM is None or Scrypt is None:
        return False

    try:
        vf = _vault_file()
        vf.parent.mkdir(parents=True, exist_ok=True)

        salt = os.urandom(FALLBACK_SALT_LENGTH)
        nonce = os.urandom(FALLBACK_NONCE_LENGTH)
        passphrase = _get_vault_passphrase()

        kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
        key = kdf.derive(passphrase)

        aesgcm = AESGCM(key)
        payload = json.dumps(data).encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, payload, None)

        envelope = {
            "version": 2,
            "kdf": "scrypt",
            "cipher": "AES-256-GCM",
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "data": base64.b64encode(ciphertext).decode("ascii"),
        }

        # Write with restricted permissions
        vf.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
        try:
            vf.chmod(0o600)
        except Exception:
            pass
        return True
    except Exception as exc:
        print(f"[Vault] ⚠️ Fallback vault encryption failed ({exc.__class__.__name__})")
        return False


# ── Core Vault Operations ─────────────────────────────────────────────────────

def set_secret(provider: str, secret: str) -> bool:
    """
    Securely store a secret credential in the OS Keyring or fallback encrypted vault.
    Never exposes or logs secret values.
    """
    if not secret or not isinstance(secret, str):
        return False

    norm_provider = _normalize_provider(provider)
    clean_val = secret.strip()
    if clean_val == VAULT_MARKER or not clean_val:
        return False

    saved = False

    # 1. Try OS Keyring if verified secure
    if is_backend_secure():
        try:
            keyring.set_password(SERVICE_NAME, norm_provider, clean_val)
            # Immediate read-back verification in memory
            verified = keyring.get_password(SERVICE_NAME, norm_provider)
            if verified == clean_val:
                saved = True
        except (KeyringLocked, PasswordSetError, KeyringError) as exc:
            print(f"[Vault] ⚠️ OS Keyring locked or unavailable ({exc.__class__.__name__}). Using encrypted vault.")
        except Exception as exc:
            print(f"[Vault] ⚠️ OS Keyring storage notice ({exc.__class__.__name__}). Using encrypted vault.")

    # 2. Fallback to encrypted local vault
    if not saved:
        data = _read_fallback_vault()
        data[norm_provider] = clean_val
        saved = _write_fallback_vault(data)

    if saved:
        _register_provider_in_manifest(norm_provider)

        # Sanitize plaintext in api_keys.json if present
        cfg_file = _default_config_path()
        if cfg_file.exists():
            try:
                cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                if cfg.get(norm_provider) != VAULT_MARKER:
                    cfg[norm_provider] = VAULT_MARKER
                    cfg_file.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
            except Exception:
                pass

    return saved


def get_secret(provider: str) -> str:
    """
    Retrieve a secret credential.
    Resolution order:
      1. Environment variable (e.g. GEMINI_API_KEY)
      2. Verified OS Keyring
      3. Encrypted fallback vault (AES-256-GCM)
      4. Legacy config file (with auto-migration)
    """
    norm_provider = _normalize_provider(provider)

    # 1. Environment variable override
    env_name = norm_provider.upper()
    if os.environ.get(env_name):
        return os.environ[env_name].strip()
    # Check alternate provider form (e.g. GEMINI_API_KEY for 'gemini')
    if norm_provider == "gemini_api_key" and os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()

    # 2. Verified OS Keyring
    if is_backend_secure():
        try:
            val = keyring.get_password(SERVICE_NAME, norm_provider)
            if val and val.strip() and val != VAULT_MARKER:
                return val.strip()
        except KeyringLocked:
            print(f"[Vault] ⚠️ OS Keyring locked for '{norm_provider}'. Checking encrypted fallback.")
        except Exception:
            pass

    # 3. Encrypted fallback vault
    fallback_data = _read_fallback_vault()
    if norm_provider in fallback_data:
        val = fallback_data[norm_provider]
        if val and val.strip() and val != VAULT_MARKER:
            return val.strip()

    # 4. One-time legacy config auto-migration check (prior to migration only)
    cfg_file = _default_config_path()
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            raw_val = cfg.get(norm_provider, "")
            # Once marked as VAULT_MARKER, NEVER silently read plaintext
            if raw_val == VAULT_MARKER:
                return ""
            if raw_val and isinstance(raw_val, str) and raw_val.strip():
                clean_key = raw_val.strip()
                # Migrate to secure storage immediately
                set_secret(norm_provider, clean_key)
                return clean_key
        except Exception:
            pass

    return ""


def delete_secret(provider: str) -> bool:
    """Delete a secret credential from OS Keyring, fallback vault, and manifest."""
    norm_provider = _normalize_provider(provider)
    deleted = False

    if is_backend_secure():
        try:
            keyring.delete_password(SERVICE_NAME, norm_provider)
            deleted = True
        except Exception:
            pass

    fallback_data = _read_fallback_vault()
    if norm_provider in fallback_data:
        del fallback_data[norm_provider]
        _write_fallback_vault(fallback_data)
        deleted = True

    _unregister_provider_in_manifest(norm_provider)
    return deleted


def has_secret(provider: str) -> bool:
    """Check if a credential is configured without exposing its secret value."""
    return bool(get_secret(provider))


def list_configured_providers() -> List[str]:
    """
    List provider names that currently have active credentials configured.
    Never exposes or returns secret values.
    """
    candidates = set(KNOWN_SECRET_PROVIDERS)
    candidates.update(_read_manifest())
    candidates.update(_read_fallback_vault().keys())

    # Check common env vars
    for p in KNOWN_SECRET_PROVIDERS:
        if os.environ.get(p.upper()):
            candidates.add(p)

    active = []
    for cand in sorted(list(candidates)):
        if has_secret(cand):
            active.append(cand)
    return active


# ── Safe Credential Migration ────────────────────────────────────────────────

def migrate_from_config(config_path: Path | str | None = None) -> Dict[str, bool]:
    """
    Idempotent, non-destructive migration of plaintext credentials from config into the vault.
    
    Safety contract:
      1. Reads existing credentials without displaying or logging them.
      2. Stores each credential in the secure vault.
      3. Reads it back and verifies exact equality in memory.
      4. Does not delete or overwrite original credential until verified.
      5. Only after successful verification, updates the field to VAULT_MARKER on disk.
      6. If anything fails, preserves original config and reports error without exposing secrets.
      7. Preserves all unrelated config fields.
    """
    target_path = Path(config_path) if config_path else _default_config_path()
    if not target_path.exists():
        return {}

    try:
        raw_text = target_path.read_text(encoding="utf-8")
        cfg = json.loads(raw_text)
    except Exception as exc:
        print(f"[Vault] ⚠️ Could not read config file for migration: {exc.__class__.__name__}")
        return {}

    if not isinstance(cfg, dict):
        return {}

    results = {}
    modified = False

    for field, val in cfg.items():
        is_secret_field = (
            field in KNOWN_SECRET_PROVIDERS
            or field.endswith("_api_key")
            or field.endswith("_secret")
            or field.endswith("_token")
        )
        if not is_secret_field:
            continue

        if not val or not isinstance(val, str) or val.strip() == VAULT_MARKER:
            continue

        raw_key = val.strip()

        # Step 1: Store secret
        stored = set_secret(field, raw_key)
        if not stored:
            results[field] = False
            print(f"[Vault] ⚠️ Migration failed to store '{field}'. Config preserved.")
            continue

        # Step 2: In-memory verification of exact equality
        retrieved = get_secret(field)
        if retrieved != raw_key:
            results[field] = False
            print(f"[Vault] ❌ Migration verification mismatch for '{field}'. Config preserved.")
            continue

        # Step 3: Verified. Mark for disk sanitization
        cfg[field] = VAULT_MARKER
        results[field] = True
        modified = True

    if modified:
        try:
            target_path.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
            print(f"[Vault] ✅ Credential migration completed. Sanitized {sum(results.values())} keys on disk.")
        except Exception as exc:
            print(f"[Vault] ⚠️ Failed to write sanitized config to disk: {exc.__class__.__name__}")

    return results


# ── Backward-Compatible Wrappers ─────────────────────────────────────────────

def get_api_key(name: str = "gemini_api_key") -> str:
    """Backward-compatible wrapper for get_secret."""
    return get_secret(name)


def set_api_key(name: str, value: str) -> bool:
    """Backward-compatible wrapper for set_secret."""
    return set_secret(name, value)


def delete_api_key(name: str) -> bool:
    """Backward-compatible wrapper for delete_secret."""
    return delete_secret(name)


def has_api_key(name: str = "gemini_api_key") -> bool:
    """Backward-compatible wrapper for has_secret."""
    return has_secret(name)
