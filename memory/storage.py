"""Atomic JSON storage, caching, indexing, backup, recovery, and migration."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import CATEGORIES, CATEGORY_FILES, MemoryRecord, normalize_category, utc_now


DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 2,
    "max_cache_categories": 5,
    "backup_interval_hours": 24,
    "backup_retention": 14,
    "temporary_memory_ttl_days": 7,
    "cleanup_after_days": 365,
    "minimum_confidence": 0.15,
    "fuzzy_threshold": 0.72,
    "max_prompt_memories": 24,
    "runtime_state": {"monitors": {}},
}


def _tokenize(text: str) -> set[str]:
    import re

    return {
        token for token in re.findall(r"[\w]+", str(text).casefold(), re.UNICODE)
        if len(token) > 1
    }


class JsonMemoryStorage:
    """Thread-safe category storage with lazy loading and an inverted index."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.backup_dir = self.root / "backups"
        self.index_path = self.root / "memory_index.json"
        self.config_path = self.root / "config.json"
        self.legacy_path = self.root / "long_term.json"
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, list[MemoryRecord]] = OrderedDict()
        self._dirty_access_ids: set[str] = set()
        self.root.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.config = self._load_or_create_config()
        self.index = self._load_or_create_index()
        self._initialize_category_files()
        self._migrate_legacy_once()
        if not self._index_consistent():
            self.rebuild_index()

    @staticmethod
    def _empty_index() -> dict[str, Any]:
        return {
            "schema_version": 2,
            "updated_at": utc_now(),
            "total_memories": 0,
            "by_id": {},
            "by_category": {category: [] for category in CATEGORIES},
            "by_token": {},
            "checksums": {},
            "audit_log": [],
        }

    def _atomic_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + f".{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with open(temp, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _read_json(path: Path) -> Any:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _load_or_create_config(self) -> dict[str, Any]:
        with self._lock:
            try:
                current = self._read_json(self.config_path) if self.config_path.exists() else {}
                if not isinstance(current, dict):
                    current = {}
            except (OSError, json.JSONDecodeError):
                current = {}
            merged = dict(DEFAULT_CONFIG)
            merged.update(current)
            state = dict(DEFAULT_CONFIG["runtime_state"])
            state.update(current.get("runtime_state", {}) if isinstance(current.get("runtime_state"), dict) else {})
            merged["runtime_state"] = state
            self._atomic_json(self.config_path, merged)
            return merged

    def _load_or_create_index(self) -> dict[str, Any]:
        with self._lock:
            try:
                index = self._read_json(self.index_path) if self.index_path.exists() else self._empty_index()
                if not isinstance(index, dict) or not isinstance(index.get("by_id"), dict):
                    raise ValueError("invalid memory index")
                return index
            except (OSError, ValueError, json.JSONDecodeError):
                index = self._empty_index()
                self._atomic_json(self.index_path, index)
                return index

    def _initialize_category_files(self) -> None:
        with self._lock:
            for category, filename in CATEGORY_FILES.items():
                path = self.root / filename
                if not path.exists():
                    self._atomic_json(path, {"schema_version": 2, "category": category, "memories": []})

    def _index_consistent(self) -> bool:
        expected = int(self.index.get("total_memories", -1))
        indexed = len(self.index.get("by_id", {}))
        return (
            expected == indexed
            and all(category in self.index.get("by_category", {}) for category in CATEGORIES)
            and all("record" in meta for meta in self.index.get("by_id", {}).values())
        )

    def _load_category_uncached(self, category: str) -> list[MemoryRecord]:
        path = self.root / CATEGORY_FILES[category]
        try:
            payload = self._read_json(path)
            if not isinstance(payload, dict) or not isinstance(payload.get("memories"), list):
                raise ValueError("invalid category payload")
            return [MemoryRecord.from_dict(item) for item in payload["memories"]]
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            if self._recover_category(category):
                payload = self._read_json(path)
                return [MemoryRecord.from_dict(item) for item in payload.get("memories", [])]
            corrupt = path.with_name(f"{path.stem}.corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
            try:
                shutil.move(path, corrupt)
            except OSError:
                pass
            self._atomic_json(path, {"schema_version": 2, "category": category, "memories": []})
            print(f"[Memory] Corrupt {category} store quarantined: {exc}")
            return []

    def load_category(self, category: str, include_archived: bool = True) -> list[MemoryRecord]:
        category = normalize_category(category)
        with self._lock:
            if category not in self._cache:
                self._cache[category] = self._load_category_uncached(category)
                while len(self._cache) > int(self.config["max_cache_categories"]):
                    self._cache.popitem(last=False)
            else:
                self._cache.move_to_end(category)
            records = self._cache[category]
            if include_archived:
                return [MemoryRecord.from_dict(record.to_dict()) for record in records]
            return [MemoryRecord.from_dict(record.to_dict()) for record in records if not record.archived]

    def save_category(self, category: str, records: Iterable[MemoryRecord]) -> None:
        category = normalize_category(category)
        records = list(records)
        payload = {
            "schema_version": 2,
            "category": category,
            "updated_at": utc_now(),
            "memories": [record.to_dict() for record in records],
        }
        with self._lock:
            path = self.root / CATEGORY_FILES[category]
            self._atomic_json(path, payload)
            self._cache[category] = [MemoryRecord.from_dict(record.to_dict()) for record in records]
            self._cache.move_to_end(category)
            self._reindex_category(category, records, self._checksum(path))
            self.backup()

    def _reindex_category(self, category: str, records: list[MemoryRecord], checksum: str) -> None:
        by_id = self.index.setdefault("by_id", {})
        old_ids = set(self.index.setdefault("by_category", {}).get(category, []))
        for memory_id in old_ids:
            by_id.pop(memory_id, None)
        category_ids = []
        for record in records:
            category_ids.append(record.id)
            by_id[record.id] = {
                "category": category,
                "key": record.key,
                "tokens": sorted(_tokenize(f"{record.key} {record.value}")),
                "updated_at": record.updated_at,
                "importance": record.importance,
                "confidence": record.confidence,
                "archived": record.archived,
                "record": record.to_dict(),
            }
        self.index["by_category"][category] = category_ids
        self.index.setdefault("checksums", {})[category] = checksum
        self._rebuild_token_index()
        self._save_index()

    def _rebuild_token_index(self) -> None:
        postings: dict[str, list[str]] = defaultdict(list)
        for memory_id, meta in self.index.get("by_id", {}).items():
            if meta.get("archived"):
                continue
            for token in set(meta.get("tokens", [])) | _tokenize(meta.get("category", "")):
                postings[token].append(memory_id)
        self.index["by_token"] = dict(postings)

    def _save_index(self) -> None:
        self.index["updated_at"] = utc_now()
        self.index["total_memories"] = len(self.index.get("by_id", {}))
        self._atomic_json(self.index_path, self.index)

    def rebuild_index(self) -> dict[str, Any]:
        with self._lock:
            audit_log = list(self.index.get("audit_log", []))
            self.index = self._empty_index()
            self.index["audit_log"] = audit_log
            for category in CATEGORIES:
                records = self._load_category_uncached(category)
                ids = []
                for record in records:
                    ids.append(record.id)
                    self.index["by_id"][record.id] = {
                        "category": category,
                        "key": record.key,
                        "tokens": sorted(_tokenize(f"{record.key} {record.value}")),
                        "updated_at": record.updated_at,
                        "importance": record.importance,
                        "confidence": record.confidence,
                        "archived": record.archived,
                        "record": record.to_dict(),
                    }
                self.index["by_category"][category] = ids
                self.index["checksums"][category] = self._checksum(self.root / CATEGORY_FILES[category])
            self._rebuild_token_index()
            self._save_index()
            return self.index

    def candidate_ids(self, query: str, category: str | None = None) -> set[str]:
        with self._lock:
            if category:
                return set(self.index.get("by_category", {}).get(normalize_category(category), []))
            tokens = _tokenize(query)
            if not tokens:
                return set(self.index.get("by_id", {}))
            posting_sets = [
                set(self.index.get("by_token", {}).get(token, []))
                for token in tokens
                if self.index.get("by_token", {}).get(token)
            ]
            if posting_sets:
                result = set.intersection(*posting_sets)
                if result:
                    return result
                result = set.union(*posting_sets)
                if result:
                    return result

            result: set[str] = set()

            # Fuzzy token lookup keeps typo search bounded by the vocabulary rather
            # than forcing a value scan across every record in a 100k-memory store.
            from difflib import SequenceMatcher

            threshold = float(self.config.get("fuzzy_threshold", 0.72))
            for indexed_token, ids in self.index.get("by_token", {}).items():
                if any(SequenceMatcher(None, token, indexed_token).ratio() >= threshold for token in tokens):
                    result.update(ids)
                    if len(result) >= 2000:
                        break
            if result:
                return result
            ranked = sorted(
                self.index.get("by_id", {}).items(),
                key=lambda pair: (pair[1].get("importance", 1), pair[1].get("updated_at", "")),
                reverse=True,
            )
            return {memory_id for memory_id, _ in ranked[:1000]}

    def get_by_ids(self, ids: Iterable[str]) -> list[MemoryRecord]:
        grouped: dict[str, set[str]] = defaultdict(set)
        snapshots: list[MemoryRecord] = []
        with self._lock:
            for memory_id in ids:
                meta = self.index.get("by_id", {}).get(memory_id)
                if meta:
                    try:
                        snapshots.append(MemoryRecord.from_dict(meta["record"]))
                    except (KeyError, TypeError, ValueError):
                        grouped[meta["category"]].add(memory_id)
        found = []
        for category, wanted in grouped.items():
            found.extend(record for record in self.load_category(category) if record.id in wanted)
        return snapshots + found

    def touch_index_records(self, ids: Iterable[str]) -> None:
        """Update access metadata in memory; maintenance flushes it to category JSON."""
        with self._lock:
            for memory_id in ids:
                meta = self.index.get("by_id", {}).get(memory_id)
                if not meta or not isinstance(meta.get("record"), dict):
                    continue
                record = MemoryRecord.from_dict(meta["record"])
                record.touch()
                meta["record"] = record.to_dict()
                self._dirty_access_ids.add(memory_id)

    def flush_accesses(self) -> int:
        with self._lock:
            dirty = set(self._dirty_access_ids)
            self._dirty_access_ids.clear()
        if not dirty:
            return 0
        grouped: dict[str, set[str]] = defaultdict(set)
        for memory_id in dirty:
            meta = self.index.get("by_id", {}).get(memory_id)
            if meta:
                grouped[meta["category"]].add(memory_id)
        for category, ids in grouped.items():
            records = self.load_category(category)
            for pos, record in enumerate(records):
                if record.id in ids:
                    records[pos] = MemoryRecord.from_dict(self.index["by_id"][record.id]["record"])
            self.save_category(category, records)
        return len(dirty)

    def all_records(self, include_archived: bool = False) -> list[MemoryRecord]:
        result = []
        for category in CATEGORIES:
            result.extend(self.load_category(category, include_archived=include_archived))
        return result

    def load_state(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.config.setdefault("runtime_state", {}).get(key, default)

    def save_state(self, key: str, value: Any) -> None:
        with self._lock:
            self.config.setdefault("runtime_state", {})[key] = value
            self._atomic_json(self.config_path, self.config)

    def append_audit(self, action: str, snapshot: dict[str, Any], **details: Any) -> None:
        """Preserve destructive-operation history outside active category stores."""
        with self._lock:
            audit = self.index.setdefault("audit_log", [])
            audit.append({"at": utc_now(), "action": action, "snapshot": snapshot, **details})
            if len(audit) > 10000:
                del audit[:-10000]
            self._save_index()

    def backup(self, force: bool = False) -> Path | None:
        with self._lock:
            marker = self.config.get("last_backup_at")
            if marker and not force:
                try:
                    elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(marker)
                    if elapsed.total_seconds() < int(self.config["backup_interval_hours"]) * 3600:
                        return None
                except (TypeError, ValueError):
                    pass
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            target = self.backup_dir / f"memory-{stamp}.zip"
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in self.root.glob("*.json"):
                    archive.write(path, arcname=path.name)
            self.config["last_backup_at"] = utc_now()
            self._atomic_json(self.config_path, self.config)
            backups = sorted(self.backup_dir.glob("memory-*.zip"), reverse=True)
            for old in backups[int(self.config["backup_retention"]):]:
                old.unlink(missing_ok=True)
            return target

    def _recover_category(self, category: str) -> bool:
        filename = CATEGORY_FILES[category]
        for backup in sorted(self.backup_dir.glob("memory-*.zip"), reverse=True):
            try:
                with zipfile.ZipFile(backup) as archive:
                    if filename not in archive.namelist():
                        continue
                    payload = json.loads(archive.read(filename).decode("utf-8"))
                    if not isinstance(payload.get("memories"), list):
                        continue
                    for item in payload["memories"]:
                        MemoryRecord.from_dict(item)
                    self._atomic_json(self.root / filename, payload)
                    print(f"[Memory] Recovered {category} from {backup.name}")
                    return True
            except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError):
                continue
        return False

    def verify_integrity(self) -> dict[str, str]:
        result: dict[str, str] = {}
        with self._lock:
            for category, filename in CATEGORY_FILES.items():
                path = self.root / filename
                try:
                    payload = self._read_json(path)
                    for item in payload.get("memories", []):
                        MemoryRecord.from_dict(item)
                    recorded = self.index.get("checksums", {}).get(category)
                    actual = self._checksum(path)
                    result[category] = "ok" if not recorded or recorded == actual else "checksum_mismatch"
                except Exception as exc:
                    result[category] = f"corrupt: {exc}"
        return result

    def _migrate_legacy_once(self) -> None:
        if not self.legacy_path.exists() or self.config.get("legacy_migrated"):
            return
        try:
            legacy = self._read_json(self.legacy_path)
            if not isinstance(legacy, dict):
                raise ValueError("legacy memory is not an object")
            for old_category, items in legacy.items():
                if old_category == "monitors" and isinstance(items, dict):
                    self.save_state("monitors", items)
                    continue
                category = normalize_category(old_category)
                records = self.load_category(category)
                if isinstance(items, dict):
                    for key, entry in items.items():
                        value = entry.get("value") if isinstance(entry, dict) else entry
                        if value not in (None, ""):
                            records.append(MemoryRecord.create(category, key, value, 0.75, 6, "legacy_migration"))
                elif old_category == "sessions" and isinstance(items, list):
                    for pos, entry in enumerate(items):
                        if isinstance(entry, dict) and entry.get("summary"):
                            records.append(MemoryRecord.create(
                                "conversation_summary", f"session_{entry.get('date', pos)}_{pos}",
                                entry["summary"], 0.8, 5, "legacy_migration",
                            ))
                if records:
                    self.save_category(category, records)
            self.config["legacy_migrated"] = True
            self.config["legacy_migrated_at"] = utc_now()
            self._atomic_json(self.config_path, self.config)
            self.backup(force=True)
            print("[Memory] Legacy long_term.json migrated to category stores.")
        except Exception as exc:
            print(f"[Memory] Legacy migration failed safely: {exc}")
