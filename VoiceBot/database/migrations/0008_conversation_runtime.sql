CREATE TABLE conversation_runtime (
 session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
 definition_json TEXT NOT NULL,
 state_json TEXT NOT NULL
);
CREATE TABLE conversation_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL,
 kind TEXT NOT NULL,
 participant_id TEXT,
 utterance_id TEXT,
 payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX conversation_events_session ON conversation_events(session_id,id);
CREATE TABLE conversation_requests (
 session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 request_id TEXT NOT NULL,
 status TEXT NOT NULL,
 result_json TEXT,
 PRIMARY KEY(session_id,request_id)
);
CREATE TABLE conversation_utterances (
 id TEXT PRIMARY KEY,
 session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 participant_id TEXT NOT NULL,
 generation_id TEXT NOT NULL,
 text TEXT NOT NULL,
 delivered_text TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'generated',
 turn_id INTEGER,
 segments_json TEXT NOT NULL DEFAULT '[]'
);
ALTER TABLE turns ADD COLUMN participant_id TEXT;
ALTER TABLE turns ADD COLUMN utterance_id TEXT;
ALTER TABLE turns ADD COLUMN original_text TEXT;
ALTER TABLE turns ADD COLUMN recognition_json TEXT;
CREATE TABLE learning_reviews (
 id TEXT PRIMARY KEY,
 user_id TEXT NOT NULL REFERENCES users(id),
 source_session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 activity_id TEXT NOT NULL,
 due_at TEXT NOT NULL,
 interval_days INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'due',
 result_session_id TEXT,
 UNIQUE(source_session_id,interval_days)
);
