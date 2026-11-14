"""
mjx.memory — Local-First Memory Foundation for MJ-X.
"""

from .database import DatabaseManager, get_db_manager, get_default_db_path
from .schema import INITIAL_SCHEMA_V1, FTS5_SCHEMA
from .normalization import normalize_text, normalize_hinglish_tokens
from .migrations import MigrationManager
from .search import MemorySearchEngine
from .repository import MemoryRepository, MemoryItem
from .backup import BackupManager, get_default_backup_dir
from .recovery import RecoveryManager

__all__ = [
    "DatabaseManager",
    "get_db_manager",
    "get_default_db_path",
    "INITIAL_SCHEMA_V1",
    "FTS5_SCHEMA",
    "normalize_text",
    "normalize_hinglish_tokens",
    "MigrationManager",
    "MemorySearchEngine",
    "MemoryRepository",
    "MemoryItem",
    "BackupManager",
    "get_default_backup_dir",
    "RecoveryManager",
]
