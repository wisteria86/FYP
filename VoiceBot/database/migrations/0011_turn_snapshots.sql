-- "Take that back": the scene state before each learner turn, so a lesson can rewind to that point.
CREATE TABLE IF NOT EXISTS turn_snapshots (
 session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 turn_id INTEGER NOT NULL,
 state_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(session_id, turn_id)
);

-- Turns taken back are kept for the record, outside the path that is assessed.
CREATE TABLE IF NOT EXISTS withdrawn_turns (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
 original_turn_id INTEGER NOT NULL,
 role TEXT NOT NULL,
 text TEXT NOT NULL,
 participant_id TEXT,
 speaker_name TEXT,
 created_at TEXT NOT NULL,
 rewind INTEGER NOT NULL,
 withdrawn_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS withdrawn_turns_session ON withdrawn_turns(session_id, rewind);

-- A practice branch started from a moment in an earlier lesson.
ALTER TABLE sessions ADD COLUMN branch_of TEXT;
ALTER TABLE sessions ADD COLUMN branch_turn_id INTEGER;
