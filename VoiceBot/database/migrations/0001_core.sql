-- Existing prototype schema, now managed as an explicit migration.
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    organization TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    title TEXT NOT NULL,
    situation TEXT NOT NULL,
    counterpart TEXT NOT NULL,
    objectives TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    duration_seconds REAL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    overall REAL NOT NULL,
    scores TEXT NOT NULL,
    strengths TEXT NOT NULL,
    improvements TEXT NOT NULL,
    evidence TEXT NOT NULL,
    feedback TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proficiency (
    user_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    score REAL NOT NULL,
    sessions INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, skill_id)
);

CREATE TABLE IF NOT EXISTS subskill_proficiency (
    user_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    subskill TEXT NOT NULL,
    score REAL NOT NULL,
    sessions INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, skill_id, subskill)
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    chunks TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posture (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    slouching REAL,
    head_position REAL,
    shoulder_alignment REAL,
    body_orientation REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_turns_session_id ON turns(session_id, id);
CREATE INDEX IF NOT EXISTS idx_documents_user_status ON documents(user_id, status);
