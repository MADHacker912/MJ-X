"""High-level long-term memory behavior for MJ."""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Iterable

from .learning import ConversationLearner
from .models import CATEGORIES, MemoryRecord, normalize_category, normalize_key, normalize_text, utc_now
from .storage import JsonMemoryStorage, _tokenize


class MemoryEngine:
    """Coordinates durable learning, retrieval, lifecycle, and maintenance."""

    def __init__(self, root: Path):
        self.storage = JsonMemoryStorage(root)
        self.learner = ConversationLearner()

    def add(
        self,
        category: str,
        key: str,
        value: Any,
        confidence: float = 0.7,
        importance: int = 5,
        source: str = "conversation",
        expires_at: str | None = None,
    ) -> MemoryRecord:
        category = normalize_category(category)
        key = normalize_key(key)
        value = str(value or "").strip()
        if not value:
            raise ValueError("Memory value cannot be empty")

        records = self.storage.load_category(category)
        exact = next((record for record in records if not record.archived and record.key == key), None)
        if exact:
            if normalize_text(exact.value) == normalize_text(value):
                exact.add_history("reinforced", source=source, previous_confidence=exact.confidence)
                exact.confidence = min(1.0, exact.confidence + max(0.03, (1.0 - exact.confidence) * 0.2))
                exact.importance = max(exact.importance, max(1, min(10, int(importance))))
                exact.updated_at = utc_now()
                exact.source = source or exact.source
                self.storage.save_category(category, records)
                return exact

            exact.add_history(
                "contradicted",
                previous_value=exact.value,
                previous_confidence=exact.confidence,
                new_value=value,
                source=source,
            )
            exact.value = value
            exact.confidence = max(0.2, min(float(confidence), exact.confidence * 0.75))
            exact.importance = max(1, min(10, int(importance)))
            exact.updated_at = utc_now()
            exact.source = source or exact.source
            exact.expires_at = expires_at
            self.storage.save_category(category, records)
            return exact

        duplicate = self._find_duplicate(records, key, value)
        if duplicate:
            duplicate.add_history("merged_duplicate", incoming_key=key, source=source)
            duplicate.confidence = min(1.0, duplicate.confidence + 0.08)
            duplicate.importance = max(duplicate.importance, max(1, min(10, int(importance))))
            duplicate.updated_at = utc_now()
            self.storage.save_category(category, records)
            return duplicate

        record = MemoryRecord.create(category, key, value, confidence, importance, source, expires_at)
        record.add_history("created", source=source)
        records.append(record)
        self.storage.save_category(category, records)
        self.storage.backup()
        return record

    @staticmethod
    def _find_duplicate(records: Iterable[MemoryRecord], key: str, value: str) -> MemoryRecord | None:
        target = normalize_text(value)
        if len(target) < 4:
            return None
        target_tokens = _tokenize(target)
        for record in records:
            if record.archived:
                continue
            key_similarity = SequenceMatcher(None, record.key, key).ratio()
            key_overlap = len(_tokenize(record.key) & _tokenize(key))
            if key_similarity < 0.72 and not key_overlap:
                continue
            existing = normalize_text(record.value)
            if existing == target:
                return record
            overlap = len(target_tokens & _tokenize(existing)) / max(1, len(target_tokens | _tokenize(existing)))
            if overlap >= 0.9 and SequenceMatcher(None, existing, target).ratio() >= 0.88:
                return record
        return None

    def update(self, memory_id: str, **changes: Any) -> MemoryRecord | None:
        meta = self.storage.index.get("by_id", {}).get(memory_id)
        if not meta:
            return None
        category = meta["category"]
        records = self.storage.load_category(category)
        record = next((item for item in records if item.id == memory_id), None)
        if not record:
            return None
        allowed = {"value", "confidence", "importance", "source", "expires_at", "key"}
        previous = {name: getattr(record, name) for name in allowed if name in changes}
        record.add_history("updated", previous=previous, source=changes.get("source", "developer_api"))
        if "value" in changes:
            record.value = str(changes["value"]).strip()
        if "confidence" in changes:
            record.confidence = max(0.0, min(1.0, float(changes["confidence"])))
        if "importance" in changes:
            record.importance = max(1, min(10, int(changes["importance"])))
        if "source" in changes:
            record.source = str(changes["source"] or record.source)[:120]
        if "expires_at" in changes:
            record.expires_at = changes["expires_at"]
        if "key" in changes:
            record.key = normalize_key(changes["key"])
        record.updated_at = utc_now()
        self.storage.save_category(category, records)
        return record

    def delete(self, memory_id: str) -> bool:
        """Soft-delete into a recoverable tombstone so history is never destroyed."""
        meta = self.storage.index.get("by_id", {}).get(memory_id)
        if not meta:
            return False
        category = meta["category"]
        records = self.storage.load_category(category)
        record = next((item for item in records if item.id == memory_id), None)
        if not record:
            return False
        self.storage.append_audit("deleted", record.to_dict())
        record.add_history("deleted")
        record.deleted = True
        record.deleted_at = utc_now()
        record.archived = True
        record.archived_at = record.deleted_at
        record.updated_at = record.deleted_at
        self.storage.save_category(category, records)
        return True

    def archive(self, memory_id: str) -> bool:
        return self._set_archive(memory_id, True)

    def restore(self, memory_id: str) -> bool:
        return self._set_archive(memory_id, False)

    def _set_archive(self, memory_id: str, archived: bool) -> bool:
        meta = self.storage.index.get("by_id", {}).get(memory_id)
        if not meta:
            return False
        records = self.storage.load_category(meta["category"])
        record = next((item for item in records if item.id == memory_id), None)
        if not record:
            return False
        record.archived = archived
        record.archived_at = utc_now() if archived else None
        if not archived:
            record.deleted = False
            record.deleted_at = None
        record.updated_at = utc_now()
        record.add_history("archived" if archived else "restored")
        self.storage.save_category(record.category, records)
        return True

    def merge(self, memory_ids: Iterable[str], key: str | None = None) -> MemoryRecord | None:
        records = self.storage.get_by_ids(memory_ids)
        records = [record for record in records if not record.archived]
        if not records:
            return None
        categories = {record.category for record in records}
        if len(categories) != 1:
            raise ValueError("Only memories from the same category can be merged")
        primary = max(records, key=lambda item: (item.importance, item.confidence, item.updated_at))
        values = []
        for record in records:
            if normalize_text(record.value) not in {normalize_text(value) for value in values}:
                values.append(record.value)
        merged_value = values[0] if len(values) == 1 else "; ".join(values)
        primary.add_history("merge_target", merged_ids=[record.id for record in records if record.id != primary.id])
        primary.value = merged_value
        primary.key = normalize_key(key or primary.key)
        primary.confidence = min(1.0, max(record.confidence for record in records) + 0.05)
        primary.importance = max(record.importance for record in records)
        primary.updated_at = utc_now()
        all_category = self.storage.load_category(primary.category)
        removed = {record.id for record in records if record.id != primary.id}
        for record in records:
            if record.id in removed:
                self.storage.append_audit("merged", record.to_dict(), target_id=primary.id)
        all_category = [record for record in all_category if record.id not in removed]
        for pos, record in enumerate(all_category):
            if record.id == primary.id:
                all_category[pos] = primary
        self.storage.save_category(primary.category, all_category)
        return primary

    def search(
        self,
        query: str = "",
        category: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_importance: int = 1,
        include_archived: bool = False,
        fuzzy: bool = True,
        limit: int = 50,
        touch: bool = False,
    ) -> list[dict[str, Any]]:
        candidate_ids = self.storage.candidate_ids(query, category)
        records = self.storage.get_by_ids(candidate_ids)
        query_norm = normalize_text(query)
        query_tokens = _tokenize(query_norm)
        ranked = []
        now = datetime.now(timezone.utc)
        for record in records:
            if record.archived and not include_archived:
                continue
            if record.importance < max(1, min(10, int(min_importance))):
                continue
            if date_from and record.updated_at[:10] < date_from[:10]:
                continue
            if date_to and record.updated_at[:10] > date_to[:10]:
                continue
            score = self.rank(record, query_norm, query_tokens, now)
            if query_norm and score < (0.18 if fuzzy else 0.3):
                continue
            ranked.append((score, record))
        ranked.sort(key=lambda pair: (pair[0], pair[1].updated_at), reverse=True)
        selected = ranked[:max(1, min(500, int(limit)))]
        if touch and selected:
            self._touch_records([record for _, record in selected])
        return [{**record.to_dict(), "relevance": round(score, 4)} for score, record in selected]

    @staticmethod
    def rank(record: MemoryRecord, query: str, query_tokens: set[str], now: datetime | None = None) -> float:
        text = normalize_text(f"{record.category} {record.key} {record.value}")
        tokens = _tokenize(text)
        lexical = len(query_tokens & tokens) / max(1, len(query_tokens)) if query_tokens else 0.5
        fuzzy = SequenceMatcher(None, query, text).ratio() if query else 0.5
        if query and query in text:
            lexical = max(lexical, 0.95)
        now = now or datetime.now(timezone.utc)
        try:
            updated = datetime.fromisoformat(record.updated_at)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now - updated).total_seconds() / 86400)
        except ValueError:
            age_days = 365
        recency = math.exp(-age_days / 365)
        importance = record.importance / 10
        access = min(1.0, math.log1p(record.access_count) / 5)
        return 0.42 * lexical + 0.16 * fuzzy + 0.17 * record.confidence + 0.14 * importance + 0.08 * recency + 0.03 * access

    def _touch_records(self, records: list[MemoryRecord]) -> None:
        self.storage.touch_index_records(record.id for record in records)

    def relevant(self, message: str, limit: int = 12) -> list[dict[str, Any]]:
        return self.search(message, limit=limit, touch=True, min_importance=2)

    def learn(self, user_message: str) -> list[MemoryRecord]:
        learned = []
        for item in self.learner.extract(user_message):
            learned.append(self.add(
                item.category, item.key, item.value, item.confidence,
                item.importance, item.source,
            ))
        return learned

    def summarize_conversation(
        self,
        conversation: str | Iterable[str],
        summarizer: Callable[[str], str] | None = None,
        max_chars: int = 1200,
    ) -> str:
        text = conversation if isinstance(conversation, str) else "\n".join(conversation)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        if summarizer:
            try:
                summary = str(summarizer(text)).strip()
                if summary:
                    return summary[:max_chars]
            except Exception:
                pass
        sentences = re.split(r"(?<=[.!?])\s+", text)
        durable = [sentence for sentence in sentences if len(sentence) > 25 and not re.match(r"^(hi|hello|hey)\b", sentence, re.I)]
        if not durable:
            durable = sentences
        return " ".join(durable[:4])[:max_chars]

    def compress(self, category: str | None = None) -> dict[str, int]:
        categories = [normalize_category(category)] if category else list(CATEGORIES)
        merged = 0
        archived = 0
        for cat in categories:
            records = self.storage.load_category(cat)
            groups: dict[tuple[str, str], list[MemoryRecord]] = {}
            for record in records:
                if not record.archived:
                    groups.setdefault((record.key, normalize_text(record.value)), []).append(record)
            for group in groups.values():
                if len(group) > 1:
                    before = len(group)
                    self.merge([record.id for record in group])
                    merged += before - 1
            records = self.storage.load_category(cat)
            for record in records:
                if len(record.history) > 80:
                    record.history = record.history[-80:]
                    archived += 1
            self.storage.save_category(cat, records)
        return {"duplicates_merged": merged, "histories_compressed": archived}

    def cleanup(self) -> dict[str, int]:
        self.storage.flush_accesses()
        now = datetime.now(timezone.utc)
        expired = 0
        low_confidence = 0
        for category in CATEGORIES:
            records = self.storage.load_category(category)
            changed = False
            for record in records:
                if record.archived:
                    continue
                expiry = None
                if record.expires_at:
                    try:
                        expiry = datetime.fromisoformat(record.expires_at)
                        if expiry.tzinfo is None:
                            expiry = expiry.replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass
                if expiry and expiry <= now:
                    record.archived = True
                    record.archived_at = utc_now()
                    record.add_history("auto_archived_expired")
                    expired += 1
                    changed = True
                elif record.confidence < float(self.storage.config["minimum_confidence"]):
                    cutoff = now - timedelta(days=int(self.storage.config["cleanup_after_days"]))
                    try:
                        updated = datetime.fromisoformat(record.updated_at)
                        if updated.tzinfo is None:
                            updated = updated.replace(tzinfo=timezone.utc)
                    except ValueError:
                        updated = now
                    if updated < cutoff:
                        record.archived = True
                        record.archived_at = utc_now()
                        record.add_history("auto_archived_low_confidence")
                        low_confidence += 1
                        changed = True
            if changed:
                self.storage.save_category(category, records)
        return {"expired_archived": expired, "low_confidence_archived": low_confidence}

    def legacy_view(self) -> dict[str, Any]:
        result: dict[str, Any] = {category: {} for category in CATEGORIES}
        for record in self.storage.all_records(include_archived=False):
            result[record.category][record.key] = {
                "id": record.id,
                "value": record.value,
                "confidence": record.confidence,
                "importance": record.importance,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "source": record.source,
                "last_accessed": record.last_accessed,
            }
        result["monitors"] = self.storage.load_state("monitors", {})
        return result

    def format_relevant_for_prompt(self, message: str, limit: int = 12) -> str:
        memories = self.relevant(message, limit)
        if not memories:
            return ""
        lines = ["[RELEVANT LONG-TERM MEMORY - use only when helpful]"]
        for memory in memories:
            lines.append(f"- {memory['category']}/{memory['key']}: {memory['value']}")
        return "\n".join(lines)
