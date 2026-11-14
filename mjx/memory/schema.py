"""
mjx.memory.schema — SQLite DDL Schemas and FTS5 Definitions.
"""

INITIAL_SCHEMA_V1 = """
-- Version tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversation Messages
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Canonical Personal Long-Term Memories
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL, -- 'preferences', 'facts', 'habits', 'projects', etc.
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    importance INTEGER DEFAULT 5,
    source TEXT DEFAULT 'direct_conversation',
    is_archived INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL
);

-- User Profile Key-Values
CREATE TABLE IF NOT EXISTS user_profile (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Memory Provenance Sources
CREATE TABLE IF NOT EXISTS memory_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    trust_score REAL DEFAULT 1.0,
    description TEXT DEFAULT ''
);

-- Scoped Tags for Memories
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    UNIQUE(memory_id, tag)
);

-- Skills & Tool Execution Metadata
CREATE TABLE IF NOT EXISTS skills_metadata (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    parameters_json TEXT DEFAULT '{}',
    enabled INTEGER DEFAULT 1,
    last_used TIMESTAMP NULL
);

-- Application Activity Events (Local Audit)
CREATE TABLE IF NOT EXISTS activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    details_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indices for rapid local retrieval
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);
CREATE INDEX IF NOT EXISTS idx_memories_archived ON memories(is_archived);
CREATE INDEX IF NOT EXISTS idx_tags_memory ON tags(memory_id);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
"""

FTS5_SCHEMA = """
-- FTS5 Full Text Search Table for Memories
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    memory_id UNINDEXED,
    category,
    key,
    value,
    tokenize='unicode61 remove_diacritics 2'
);

-- FTS5 Full Text Search Table for Conversation Messages
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    message_id UNINDEXED,
    role,
    content,
    tokenize='unicode61 remove_diacritics 2'
);
"""
