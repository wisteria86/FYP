-- Normalized platform foundation. Legacy tables remain available during migration.
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organization_memberships (
    organization_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('owner','admin','learner')),
    created_at TEXT NOT NULL,
    PRIMARY KEY(organization_id, user_id),
    FOREIGN KEY(organization_id) REFERENCES organizations(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    preferred_language TEXT NOT NULL DEFAULT 'English',
    captions_enabled INTEGER NOT NULL DEFAULT 1,
    selected_tts_engine TEXT,
    selected_tts_voice TEXT,
    notification_settings_json TEXT NOT NULL DEFAULT '{}',
    privacy_settings_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS skill_catalog (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'workplace',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subskill_catalog (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(skill_id, name),
    FOREIGN KEY(skill_id) REFERENCES skill_catalog(id)
);

CREATE TABLE IF NOT EXISTS training_activities (
    id TEXT PRIMARY KEY,
    organization_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    primary_skill_id TEXT NOT NULL,
    scenario_type TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK(difficulty IN ('beginner','intermediate','advanced','adaptive')),
    estimated_minutes INTEGER NOT NULL,
    guided_mode INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(organization_id) REFERENCES organizations(id),
    FOREIGN KEY(primary_skill_id) REFERENCES skill_catalog(id)
);

CREATE TABLE IF NOT EXISTS activity_subskills (
    activity_id TEXT NOT NULL,
    subskill_id TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1,
    PRIMARY KEY(activity_id, subskill_id),
    FOREIGN KEY(activity_id) REFERENCES training_activities(id),
    FOREIGN KEY(subskill_id) REFERENCES subskill_catalog(id)
);

CREATE TABLE IF NOT EXISTS scenario_templates (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL,
    learner_role TEXT NOT NULL,
    context TEXT NOT NULL,
    objectives_json TEXT NOT NULL,
    success_criteria_json TEXT NOT NULL,
    failure_patterns_json TEXT NOT NULL DEFAULT '[]',
    opening_situation TEXT NOT NULL,
    participants_json TEXT NOT NULL,
    variables_json TEXT NOT NULL DEFAULT '{}',
    rubric_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(activity_id) REFERENCES training_activities(id)
);

CREATE TABLE IF NOT EXISTS training_session_participants (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    participant_type TEXT NOT NULL CHECK(participant_type IN ('learner','ai')),
    display_name TEXT NOT NULL,
    scenario_role TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    configuration_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_id TEXT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS assessment_metrics (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL,
    skill_id TEXT,
    subskill_id TEXT,
    metric_name TEXT NOT NULL,
    score REAL NOT NULL CHECK(score >= 0 AND score <= 100),
    rationale TEXT NOT NULL,
    FOREIGN KEY(assessment_id) REFERENCES assessments(id),
    FOREIGN KEY(skill_id) REFERENCES skill_catalog(id),
    FOREIGN KEY(subskill_id) REFERENCES subskill_catalog(id)
);

CREATE TABLE IF NOT EXISTS assessment_evidence (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL,
    turn_id INTEGER,
    evidence_type TEXT NOT NULL,
    observation TEXT NOT NULL,
    better_response TEXT,
    FOREIGN KEY(assessment_id) REFERENCES assessments(id),
    FOREIGN KEY(turn_id) REFERENCES turns(id)
);

CREATE TABLE IF NOT EXISTS proficiency_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    subskill_id TEXT,
    session_id TEXT,
    previous_score REAL NOT NULL,
    observed_score REAL NOT NULL,
    new_score REAL NOT NULL,
    confidence REAL NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(skill_id) REFERENCES skill_catalog(id),
    FOREIGN KEY(subskill_id) REFERENCES subskill_catalog(id),
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS user_goals (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    target_date TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS training_plans (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal_id TEXT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    generated_reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(goal_id) REFERENCES user_goals(id)
);

CREATE TABLE IF NOT EXISTS training_plan_phases (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    position INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'upcoming',
    FOREIGN KEY(plan_id) REFERENCES training_plans(id)
);

CREATE TABLE IF NOT EXISTS training_plan_activities (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    phase_id TEXT,
    activity_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'upcoming',
    session_id TEXT,
    due_at TEXT,
    FOREIGN KEY(plan_id) REFERENCES training_plans(id),
    FOREIGN KEY(phase_id) REFERENCES training_plan_phases(id),
    FOREIGN KEY(activity_id) REFERENCES training_activities(id),
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    priority REAL NOT NULL DEFAULT 0,
    source_assessment_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    expires_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(activity_id) REFERENCES training_activities(id),
    FOREIGN KEY(source_assessment_id) REFERENCES assessments(id)
);

CREATE TABLE IF NOT EXISTS resources (
    id TEXT PRIMARY KEY,
    organization_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    content_url TEXT,
    content_text TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(organization_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS resource_skill_links (
    resource_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    subskill_id TEXT,
    PRIMARY KEY(resource_id, skill_id, subskill_id),
    FOREIGN KEY(resource_id) REFERENCES resources(id),
    FOREIGN KEY(skill_id) REFERENCES skill_catalog(id),
    FOREIGN KEY(subskill_id) REFERENCES subskill_catalog(id)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding_ref TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(document_id, position),
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_events_session_created ON session_events(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_history_user_created ON proficiency_history(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_activities_skill_active ON training_activities(primary_skill_id, active);
CREATE INDEX IF NOT EXISTS idx_recommendations_user_status ON recommendations(user_id, status, priority DESC);
