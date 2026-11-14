"""
Comprehensive verification suite for MJ-X P1 Cortex Runtime Unification.
Tests the 14 mandatory integration scenarios across SQLite WAL, FTS5, legacy JSON migration,
backward-compatible memory_manager facade, resilience, and recovery.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sqlite3
import tempfile
import threading
from pathlib import Path
import pytest

from mjx.memory import (
    DatabaseManager,
    MemoryRepository,
    MemoryItem,
    MigrationManager,
    BackupManager,
    RecoveryManager,
)
from memory import memory_manager


@pytest.fixture
def cortex_env(tmp_path):
    """Create isolated database and memory environment for cortex integration tests."""
    db_path = tmp_path / "cortex_test.db"
    db_mgr = DatabaseManager(db_path)
    repo = MemoryRepository(db_mgr)
    old_repo = memory_manager._repo
    old_db = memory_manager._db_manager
    memory_manager.set_repository(repo)
    memory_manager._db_manager = db_mgr
    yield repo, tmp_path
    memory_manager.set_repository(old_repo)
    memory_manager._db_manager = old_db


# ── Scenario 1: Fresh startup with empty DB ──────────────────────────────────
def test_scenario_01_fresh_startup_empty_db(tmp_path):
    """Verify DB, WAL, FTS5, and schema migrations initialize cleanly on empty start."""
    db_path = tmp_path / "fresh_mjx.db"
    db_mgr = DatabaseManager(db_path)
    repo = MemoryRepository(db_mgr)

    conn = db_mgr.get_connection()
    cursor = conn.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"

    cursor = conn.execute("PRAGMA foreign_keys;")
    assert cursor.fetchone()[0] == 1

    ok, msg = db_mgr.check_integrity()
    assert ok is True
    assert msg == "ok"

    # Check required tables exist
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('memories', 'conversations', 'messages', 'memories_fts', 'messages_fts');"
    )
    names = {row[0] for row in cursor.fetchall()}
    assert names == {'memories', 'conversations', 'messages', 'memories_fts', 'messages_fts'}


# ── Scenario 2: Existing JSON migration ──────────────────────────────────────
def test_scenario_02_existing_json_migration(cortex_env):
    """Verify importing records from real memory/*.json into SQLite preserves data."""
    repo, tmp_path = cortex_env
    # Create fake legacy memory dir with schema v2 format
    legacy_dir = tmp_path / "legacy_mem"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    skills_json = legacy_dir / "skills.json"
    skills_json.write_text(
        '{"schema_version": 2, "category": "skills", "memories": ['
        '{"key": "python_expert", "value": "Proficient in Python and AsyncIO", "confidence": 0.95, "importance": 8},'
        '{"key": "rust_basics", "value": "Learning Rust memory model", "confidence": 0.75, "importance": 6}'
        ']}',
        encoding="utf-8",
    )

    imported = repo.import_legacy_json_memories(legacy_dir)
    assert imported == 2

    # Verify both records loaded into SQLite
    memories = repo.list_memories(category="skills")
    assert len(memories) == 2
    keys = {m.key for m in memories}
    assert "python_expert" in keys
    assert "rust_basics" in keys

    # Verify original file was NEVER deleted
    assert skills_json.exists()


# ── Scenario 3: Idempotent repeated migration ────────────────────────────────
def test_scenario_03_idempotent_repeated_migration(cortex_env):
    """Verify running migration repeatedly does not duplicate records."""
    repo, tmp_path = cortex_env
    legacy_dir = tmp_path / "legacy_mem_idempotent"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    notes_json = legacy_dir / "notes.json"
    notes_json.write_text(
        '{"schema_version": 2, "category": "notes", "memories": ['
        '{"key": "user_birthday", "value": "October 24", "confidence": 0.9, "importance": 7}'
        ']}',
        encoding="utf-8",
    )

    first_run = repo.import_legacy_json_memories(legacy_dir)
    assert first_run == 1
    assert len(repo.list_memories(category="notes")) == 1

    second_run = repo.import_legacy_json_memories(legacy_dir)
    assert second_run == 1
    # Record count must strictly remain 1
    assert len(repo.list_memories(category="notes")) == 1


# ── Scenario 4: Application restart & persistence ─────────────────────────────
def test_scenario_04_restart_and_persistence(tmp_path):
    """Verify data saved in session 1 persists across application restart in session 2."""
    db_path = tmp_path / "persistent.db"

    # Session 1: Save data
    db_mgr_1 = DatabaseManager(db_path)
    repo_1 = MemoryRepository(db_mgr_1)
    repo_1.save_memory("preferences", "theme", "cyberpunk_dark", confidence=0.99, importance=9)

    # Session 2: Fresh instances pointing to same file
    db_mgr_2 = DatabaseManager(db_path)
    repo_2 = MemoryRepository(db_mgr_2)
    memories = repo_2.list_memories(category="preferences")
    assert len(memories) == 1
    assert memories[0].key == "theme"
    assert memories[0].value == "cyberpunk_dark"
    assert memories[0].importance == 9


# ── Scenario 5: Conversation memory persistence ──────────────────────────────
def test_scenario_05_conversation_memory_persistence(cortex_env):
    """Verify conversations, message turns, and summaries are logged and retrievable."""
    repo, _ = cortex_env
    conv_id = memory_manager.start_conversation("Work Chat Session")
    assert conv_id

    # Add turns
    msg1_id = memory_manager.add_conversation_message(conv_id, "user", "What is our architecture plan?")
    msg2_id = memory_manager.add_conversation_message(conv_id, "assistant", "Local-first SQLite with WAL mode.")
    assert msg1_id and msg2_id

    # Retrieve messages
    messages = memory_manager.get_conversation_messages(conv_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert "architecture plan" in messages[0]["content"]
    assert messages[1]["role"] == "assistant"
    assert "Local-first" in messages[1]["content"]

    # Update summary
    updated = memory_manager.update_conversation_summary(conv_id, "Discussed architecture plan.")
    assert updated is True
    conv = repo.get_conversation(conv_id)
    assert conv["summary"] == "Discussed architecture plan."


# ── Scenario 6: Hinglish memory retrieval ─────────────────────────────────────
def test_scenario_06_hinglish_memory_retrieval(cortex_env):
    """Verify FTS5 query with colloquial Hinglish tokens retrieves relevant memories."""
    repo, _ = cortex_env
    memory_manager.saveMemory({
        "category": "habits",
        "key": "exercise",
        "value": "Roz subah jaldi uth kar gym karna chahiye",
        "importance": 8,
    })

    # Search with colloquial spelling 'krna' (should normalize to 'karna')
    results = memory_manager.searchMemory("gym krna", category="habits")
    assert len(results) >= 1
    assert results[0]["key"] == "exercise"
    assert "gym" in results[0]["value"]


# ── Scenario 7: Database unavailable fallback ─────────────────────────────────
def test_scenario_07_database_unavailable_fallback(cortex_env):
    """Verify memory_manager gracefully falls back to legacy engine when DB is unavailable."""
    # Temporarily set repo to None to simulate complete DB unavailability
    memory_manager.set_repository(None)

    # loadMemory should not crash
    res = memory_manager.loadMemory("notes")
    assert isinstance(res, list)

    # saveMemory should save to legacy engine without crashing
    saved = memory_manager.saveMemory({"category": "notes", "key": "fallback_test", "value": "safe"})
    assert saved["key"] == "fallback_test"
    assert saved["value"] == "safe"


# ── Scenario 8: Corrupted database recovery ───────────────────────────────────
def test_scenario_08_corrupted_database_recovery(tmp_path):
    """Verify integrity check detects corruption and RecoveryManager restores from valid backup."""
    db_path = tmp_path / "corrupt_test.db"
    db_mgr = DatabaseManager(db_path)
    repo = MemoryRepository(db_mgr)
    repo.save_memory("facts", "gravity", "9.8 m/s2")

    # Create backup before corruption
    backup_mgr = BackupManager(db_mgr, backup_dir=tmp_path / "backups")
    backup_file = backup_mgr.create_backup()
    assert backup_file.exists()

    # Checkpoint WAL and close before testing corruption
    conn = db_mgr.get_connection()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    db_mgr.close()

    # Corrupt database header deliberately
    with open(db_path, "r+b") as f:
        f.seek(0)
        f.write(b"CORRUPT_HEADER_NOT_SQLITE_FILE" * 5)

    # Check integrity fails
    corrupt_mgr = DatabaseManager(db_path)
    ok, _ = corrupt_mgr.check_integrity()
    assert ok is False

    # Restore from verified backup
    recovery = RecoveryManager(corrupt_mgr)
    restored = recovery.restore_backup(backup_file)
    assert restored is True

    # Check integrity restored
    fresh_mgr = DatabaseManager(db_path)
    ok, msg = fresh_mgr.check_integrity()
    assert ok is True
    assert msg == "ok"


# ── Scenario 9: Online backup creation ────────────────────────────────────────
def test_scenario_09_online_backup_creation(cortex_env):
    """Verify backupMemory creates verified, consistent point-in-time snapshot."""
    repo, tmp_path = cortex_env
    repo.save_memory("preferences", "font", "JetBrains Mono", importance=7)

    backup_path = memory_manager.backupMemory()
    assert backup_path is not None
    p = Path(backup_path)
    assert p.exists()
    assert p.stat().st_size > 0

    # Verify backup integrity
    recovery = RecoveryManager(repo.db)
    valid, msg = recovery.verify_backup(p)
    assert valid is True


# ── Scenario 10: Backup restoration verification ──────────────────────────────
def test_scenario_10_backup_restoration_verification(tmp_path):
    """Verify restoring a backup restores all tables, rows, and FTS5 indices."""
    db_path = tmp_path / "restore_test.db"
    db_mgr = DatabaseManager(db_path)
    repo = MemoryRepository(db_mgr)

    repo.save_memory("facts", "speed_of_light", "299792458 m/s")
    conv_id = repo.start_conversation("Physics")
    repo.add_message(conv_id, "user", "What is c?")

    backup_mgr = BackupManager(db_mgr, backup_dir=tmp_path / "backups")
    backup_file = backup_mgr.create_backup()

    # Clear active database
    repo.delete_memory(repo.list_memories()[0].id, hard_delete=True)
    repo.clear_conversation(conv_id)
    assert len(repo.list_memories()) == 0

    # Restore
    recovery = RecoveryManager(db_mgr)
    assert recovery.restore_backup(backup_file) is True

    # Verify rows & FTS restored
    reloaded_repo = MemoryRepository(db_mgr)
    memories = reloaded_repo.list_memories()
    assert len(memories) >= 1
    assert memories[0].key == "speed_of_light"
    search_res = reloaded_repo.search_engine.search_memories("light")
    assert len(search_res) >= 1


# ── Scenario 11: Memory deletion from tables & FTS5 ───────────────────────────
def test_scenario_11_deletion_and_fts5_sync(cortex_env):
    """Verify soft delete archives and hard delete cleans both table and FTS5."""
    repo, _ = cortex_env
    saved = memory_manager.saveMemory({"category": "notes", "key": "temp_secret", "value": "classified_123"})
    m_id = saved["id"]

    # FTS5 finds it initially
    assert len(memory_manager.searchMemory("classified_123")) >= 1

    # Soft delete (archive)
    memory_manager.archiveMemory(m_id)
    active = memory_manager.loadMemory("notes", include_archived=False)
    assert not any(m["id"] == m_id for m in active)

    # Hard delete
    memory_manager.deleteMemory(m_id, hard_delete=True)
    all_mems = memory_manager.loadMemory("notes", include_archived=True)
    assert not any(m["id"] == m_id for m in all_mems)

    # FTS5 no longer finds it
    assert len(memory_manager.searchMemory("classified_123")) == 0


# ── Scenario 12: Concurrent multi-thread memory operations ────────────────────
def test_scenario_12_concurrent_multithread_operations(cortex_env):
    """Verify thread safety with concurrent writers and readers."""
    repo, _ = cortex_env
    errors: list[Exception] = []

    def writer(idx: int):
        try:
            for j in range(5):
                memory_manager.saveMemory({
                    "category": "threads",
                    "key": f"key_{idx}_{j}",
                    "value": f"value_{idx}_{j}",
                    "importance": 5,
                })
        except Exception as exc:
            errors.append(exc)

    def reader():
        try:
            for _ in range(10):
                memory_manager.loadMemory("threads")
                memory_manager.searchMemory("value")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    threads.extend([threading.Thread(target=reader) for _ in range(2)])

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert not errors, f"Concurrent thread errors: {errors}"
    items = memory_manager.loadMemory("threads")
    assert len(items) == 20  # 4 writers * 5 items


# ── Scenario 13: UI non-blocking responsiveness ───────────────────────────────
@pytest.mark.asyncio
async def test_scenario_13_async_non_blocking_responsiveness(cortex_env):
    """Verify async memory functions run via worker threads without blocking."""
    saved = await memory_manager.saveMemoryAsync({
        "category": "async_test",
        "key": "async_key",
        "value": "async_value",
        "importance": 6,
    })
    assert saved["key"] == "async_key"

    loaded = await memory_manager.loadMemoryAsync("async_test")
    assert len(loaded) >= 1

    searched = await memory_manager.searchMemoryAsync("async_value", category="async_test")
    assert len(searched) >= 1
    assert searched[0]["key"] == "async_key"


# ── Scenario 14: Legacy compatibility across all memory_manager functions ─────
def test_scenario_14_legacy_compatibility_suite(cortex_env):
    """Verify load_memory, update_memory, remember, forget, pop_last_session, etc. work seamlessly."""
    # 1. remember & forget
    rem_msg = memory_manager.remember("pet", "golden_retriever", "facts")
    assert "Remembered:" in rem_msg

    loaded = memory_manager.load_memory()
    assert loaded["facts"]["pet"]["value"] == "golden_retriever"

    f_msg = memory_manager.forget("pet", "facts")
    assert "Forgotten:" in f_msg

    # 2. update_memory
    memory_manager.update_memory({"projects": {"mjx": {"value": "Autonomous assistant"}}})
    mems = memory_manager.loadMemory("projects")
    assert any(m["key"] == "mjx" and m["value"] == "Autonomous assistant" for m in mems)

    # 3. format_memory_for_prompt
    formatted = memory_manager.format_memory_for_prompt()
    assert "LONG-TERM MEMORY" in formatted
    assert "projects/mjx: Autonomous assistant" in formatted

    # 4. save_state & load_state
    memory_manager.save_state("theme_mode", {"dark": True})
    state = memory_manager.load_state("theme_mode")
    assert state == {"dark": True}

    # 5. save_session_summary & pop_last_session
    memory_manager.save_session_summary("User completed task and discussed architecture.", "English")
    popped = memory_manager.pop_last_session()
    assert popped is not None
    assert "architecture" in popped["summary"]
    assert popped["language"] == "English"
    # Popping marks it archived so a second pop returns None (or next one)
    second_pop = memory_manager.pop_last_session()
    assert second_pop is None
