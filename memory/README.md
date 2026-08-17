# MJ Long-Term Memory

The memory package stores durable user knowledge in category-specific JSON files.
`memory_index.json` contains searchable metadata and an inverted token index. Writes
are atomic, category data is loaded lazily, and automatic ZIP backups are retained in
`memory/backups/`.

## Record Contract

Every record includes `id`, `category`, `key`, `value`, `confidence`, `importance`,
`created_at`, `updated_at`, `source`, and `last_accessed`. Lifecycle fields and an
append-only per-record `history` support archive, restore, contradiction tracking,
and recoverable deletion.

## API

Import public functions from `memory`:

```python
from memory import getRelevantMemory, saveMemory

saveMemory({
    "category": "preferences",
    "key": "editor",
    "value": "VS Code",
    "confidence": 0.9,
    "importance": 7,
    "source": "explicit_user_statement",
})

matches = getRelevantMemory("Which editor does the user prefer?", limit=8)
```

The complete synchronous API is `loadMemory`, `saveMemory`, `searchMemory`,
`updateMemory`, `deleteMemory`, `archiveMemory`, `restoreMemory`, `mergeMemory`,
`summarizeConversation`, `compressMemory`, `backupMemory`, `rankMemory`, and
`getRelevantMemory`. Corresponding `*Async` functions are available from
`memory.memory_manager` and run disk work outside the caller's event loop.

## Recovery

Call `verifyMemoryIntegrity()` for schema and checksum validation. Invalid JSON is
recovered from the newest valid backup when possible; otherwise it is quarantined as
`*.corrupt-<timestamp>.json` and replaced with an empty valid store. The old
`long_term.json` is migrated once and retained unchanged as a migration source.
