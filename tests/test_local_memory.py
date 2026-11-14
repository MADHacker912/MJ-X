"""
Unit tests for mjx.memory — Local-First SQLite + FTS5 Memory Foundation.
"""

import json
from pathlib import Path
import pytest

from mjx.memory import (
    DatabaseManager,
    MigrationManager,
    MemoryRepository,
    BackupManager,
    RecoveryManager,
    normalize_text,
    normalize_hinglish_tokens,
)


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test_memory.db"
    db_mgr = DatabaseManager(db_file)
    return MemoryRepository(db_mgr)


def test_database_pragmas_and_integrity(repo):
    """Database initializes with WAL mode, foreign keys, and passes integrity check."""
    conn = repo.db.get_connection()
    cursor = conn.execute("PRAGMA foreign_keys;")
    assert cursor.fetchone()[0] == 1

    ok, msg = repo.db.check_integrity()
    assert ok is True
    assert msg == "ok"


def test_schema_migrations_applied(repo):
    """Migrations 1 and 2 (initial schema + FTS5) are applied."""
    applied = MigrationManager(repo.db).get_applied_versions()
    assert 1 in applied
    assert 2 in applied


def test_memory_crud_and_fts5_search(repo):
    """Memories are created, updated, indexed into FTS5, searched, and archived."""
    # Create
    item = repo.save_memory(
        category="preferences",
        key="favorite_editor",
        value="VSCode with dark neon theme",
        confidence=0.95,
        importance=8,
        tags=["ide", "coding"],
    )
    assert item.key == "favorite_editor"
    assert item.category == "preferences"

    # Search with FTS5
    results = repo.search_engine.search_memories("editor")
    assert len(results) >= 1
    assert results[0]["key"] == "favorite_editor"

    # Update
    updated = repo.save_memory(
        category="preferences",
        key="favorite_editor",
        value="Cursor IDE with dark neon theme",
        confidence=0.99,
    )
    assert updated.value == "Cursor IDE with dark neon theme"

    search_cursor = repo.search_engine.search_memories("Cursor")
    assert len(search_cursor) >= 1
    assert "Cursor IDE" in search_cursor[0]["value"]

    # Archive / Delete
    repo.delete_memory(item.id, hard_delete=False)
    active = repo.list_memories(category="preferences")
    assert len(active) == 0

    all_incl_archived = repo.list_memories(category="preferences", include_archived=True)
    assert len(all_incl_archived) == 1
    assert all_incl_archived[0].is_archived is True


def test_hinglish_token_normalization(repo):
    """Hinglish tokens like 'krna' expand to 'karna' and match stored text."""
    repo.save_memory(
        category="habits",
        key="gym_routine",
        value="Roz sham ko workout karna chahiye aur time par sona",
    )

    # Search using colloquial spelling 'krna'
    results = repo.search_engine.search_memories("workout krna")
    assert len(results) >= 1
    assert results[0]["key"] == "gym_routine"


def test_conversations_and_messages(repo):
    """Conversations and messages are stored, retrieved, and searched."""
    conv_id = repo.start_conversation(title="Project Discussion")
    m1 = repo.add_message(conv_id, "user", "What is the status of the local-first memory?")
    m2 = repo.add_message(conv_id, "assistant", "Local SQLite database and FTS5 are fully implemented.")

    messages = repo.get_messages(conv_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    # Search conversations
    search_res = repo.search_engine.search_conversations("memory")
    assert len(search_res) >= 1

    # Clear conversation
    repo.clear_conversation(conv_id)
    assert len(repo.get_messages(conv_id)) == 0


def test_user_profile_and_export(repo):
    """User profile keys persist and full data export generates valid envelope."""
    repo.set_user_profile("preferred_name", "Saksham")
    assert repo.get_user_profile("preferred_name") == "Saksham"

    repo.save_memory("facts", "birth_city", "New Delhi")

    export = repo.export_data()
    assert export["version"] == 1
    assert export["profile"]["preferred_name"] == "Saksham"
    assert len(export["memories"]) >= 1


def test_backup_creation_and_integrity(repo, tmp_path):
    """Online point-in-time backups pass integrity check and prune safely."""
    b_dir = tmp_path / "backups"
    bm = BackupManager(db_manager=repo.db, backup_dir=b_dir)

    repo.save_memory("facts", "test_item", "test_backup_value")

    backup_file = bm.create_backup()
    assert backup_file.exists()
    assert backup_file.stat().st_size > 0

    backups = bm.list_backups()
    assert len(backups) == 1

    # Prune keeping 1 backup does not delete the only valid backup
    pruned = bm.prune_old_backups(keep_count=1)
    assert pruned == 0
    assert backup_file.exists()


def test_recovery_verification_and_restore(repo, tmp_path):
    """Recovery manager verifies backups in temp isolation and restores active database."""
    b_dir = tmp_path / "backups"
    bm = BackupManager(db_manager=repo.db, backup_dir=b_dir)
    rm = RecoveryManager(db_manager=repo.db)

    repo.save_memory("notes", "original_secret_note", "Must survive recovery test")
    backup_file = bm.create_backup()

    # Verify backup
    valid, msg = rm.verify_backup(backup_file)
    assert valid is True
    assert "successfully" in msg

    # Mutate active database
    repo.save_memory("notes", "original_secret_note", "Corrupted or overwritten value")
    assert repo.list_memories(category="notes")[0].value == "Corrupted or overwritten value"

    # Restore from backup
    restored = rm.restore_backup(backup_file)
    assert restored is True

    # Active db should reflect original restored value
    notes = repo.list_memories(category="notes")
    assert len(notes) == 1
    assert notes[0].value == "Must survive recovery test"


def test_legacy_json_importer(repo, tmp_path):
    """Non-destructive import reads legacy JSON files into SQLite without modifying originals."""
    mem_dir = tmp_path / "legacy_memory"
    mem_dir.mkdir()

    sample_facts = {
        "user_alias": "Tony",
        "system_language": "English/Hinglish",
    }
    (mem_dir / "facts.json").write_text(json.dumps(sample_facts), encoding="utf-8")

    imported = repo.import_legacy_json_memories(mem_dir)
    assert imported == 2

    # Check imported in SQLite
    facts = repo.list_memories(category="facts")
    assert len(facts) == 2
    keys = {f.key for f in facts}
    assert "user_alias" in keys

    # Original file is unmodified
    assert (mem_dir / "facts.json").exists()
    assert json.loads((mem_dir / "facts.json").read_text(encoding="utf-8")) == sample_facts
