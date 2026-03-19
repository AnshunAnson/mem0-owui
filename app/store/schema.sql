PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS memory_events (
    event_id TEXT PRIMARY KEY,
    dedupe_key TEXT NOT NULL UNIQUE,
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    event_schema_version TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    next_retry_at TEXT,
    dead_lettered_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_candidates (
    candidate_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    candidate_version INTEGER NOT NULL,
    candidate_hash TEXT NOT NULL,
    candidate_json TEXT NOT NULL,
    candidate_schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (event_id, candidate_version),
    FOREIGN KEY(event_id) REFERENCES memory_events(event_id)
);

CREATE TABLE IF NOT EXISTS memory_audits (
    audit_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    audit_result TEXT NOT NULL,
    audit_json TEXT NOT NULL,
    audit_schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES memory_events(event_id),
    FOREIGN KEY(candidate_id) REFERENCES memory_candidates(candidate_id)
);

CREATE TABLE IF NOT EXISTS memory_applies (
    apply_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    final_action TEXT NOT NULL,
    target_id TEXT,
    mem0_memory_id TEXT,
    apply_status TEXT NOT NULL,
    graph_degraded INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES memory_events(event_id),
    FOREIGN KEY(candidate_id) REFERENCES memory_candidates(candidate_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_events_status_retry
ON memory_events(status, next_retry_at);

CREATE INDEX IF NOT EXISTS idx_memory_events_conversation
ON memory_events(conversation_id);

CREATE INDEX IF NOT EXISTS idx_memory_events_user_created
ON memory_events(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_memory_candidates_event
ON memory_candidates(event_id);

CREATE INDEX IF NOT EXISTS idx_memory_audits_event
ON memory_audits(event_id);

CREATE INDEX IF NOT EXISTS idx_memory_audits_candidate
ON memory_audits(candidate_id);

CREATE INDEX IF NOT EXISTS idx_memory_applies_event
ON memory_applies(event_id);

CREATE INDEX IF NOT EXISTS idx_memory_applies_candidate
ON memory_applies(candidate_id);

CREATE INDEX IF NOT EXISTS idx_memory_applies_target
ON memory_applies(target_id);

