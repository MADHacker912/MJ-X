from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from memory.engine import MemoryEngine
from memory.models import CATEGORIES


class MemoryEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engine = MemoryEngine(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_creates_required_store_structure_and_record_fields(self):
        record = self.engine.add("identity", "name", "Saksham", 0.95, 10, "test")
        required = {
            "id", "category", "key", "value", "confidence", "importance",
            "created_at", "updated_at", "source", "last_accessed",
        }
        self.assertTrue(required.issubset(record.to_dict()))
        for category in CATEGORIES:
            self.assertTrue((self.root / f"{category}.json").exists())
        self.assertTrue((self.root / "memory_index.json").exists())
        self.assertTrue((self.root / "config.json").exists())

    def test_repetition_deduplicates_and_increases_confidence(self):
        first = self.engine.add("preferences", "editor", "VS Code", 0.7, 7, "first")
        second = self.engine.add("preferences", "editor", "VS Code", 0.7, 7, "repeat")
        self.assertEqual(first.id, second.id)
        self.assertGreater(second.confidence, first.confidence)
        self.assertEqual(1, self.engine.storage.index["total_memories"])

    def test_contradiction_updates_value_and_preserves_history(self):
        first = self.engine.add("locations", "home", "Delhi", 0.9, 8, "first")
        changed = self.engine.add("locations", "home", "Mumbai", 0.9, 8, "correction")
        self.assertEqual(first.id, changed.id)
        self.assertEqual("Mumbai", changed.value)
        self.assertLess(changed.confidence, 0.9)
        event = changed.history[-1]
        self.assertEqual("contradicted", event["action"])
        self.assertEqual("Delhi", event["previous_value"])

    def test_search_ranking_filters_and_access_tracking(self):
        project = self.engine.add("projects", "mj", "Build the MJ memory engine", 0.95, 10, "test")
        self.engine.add("preferences", "drink", "Coffee", 0.8, 4, "test")
        results = self.engine.search("MJ memory project", min_importance=8, touch=True)
        self.assertEqual(project.id, results[0]["id"])
        touched = self.engine.storage.get_by_ids([project.id])[0]
        self.assertEqual(1, touched.access_count)

    def test_archive_restore_and_delete_audit(self):
        record = self.engine.add("notes", "durable", "Keep this", 0.8, 5, "test")
        self.assertTrue(self.engine.archive(record.id))
        self.assertEqual([], self.engine.search(category="notes"))
        self.assertTrue(self.engine.restore(record.id))
        self.assertTrue(self.engine.delete(record.id))
        self.assertEqual("deleted", self.engine.storage.index["audit_log"][-1]["action"])

    def test_learning_is_conservative(self):
        self.assertEqual([], self.engine.learn("Hello"))
        learned = self.engine.learn("My favourite editor is VS Code")
        self.assertEqual(1, len(learned))
        self.assertEqual("preferences", learned[0].category)
        self.assertEqual("VS Code", learned[0].value)

    def test_backup_recovers_corrupt_category(self):
        record = self.engine.add("facts", "answer", "42", 0.9, 8, "test")
        self.engine.storage.backup(force=True)
        (self.root / "facts.json").write_text("{broken", encoding="utf-8")
        recovered = MemoryEngine(self.root).storage.load_category("facts")
        self.assertEqual(record.id, recovered[0].id)

    def test_legacy_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "long_term.json").write_text(json.dumps({
                "identity": {"name": {"value": "Saksham"}},
                "wishes": {"travel": {"value": "Visit Japan"}},
                "monitors": {"ai": {"topic": "AI"}},
            }), encoding="utf-8")
            engine = MemoryEngine(root)
            self.assertEqual("Saksham", engine.search("name", category="identity")[0]["value"])
            self.assertEqual("Visit Japan", engine.search("travel", category="goals")[0]["value"])
            self.assertIn("ai", engine.storage.load_state("monitors"))


if __name__ == "__main__":
    unittest.main()
