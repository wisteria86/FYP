CREATE TABLE IF NOT EXISTS document_organizations (
    document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id)
);
INSERT OR IGNORE INTO document_organizations(document_id,organization_id)
SELECT d.id,m.organization_id FROM documents d JOIN organization_memberships m ON m.user_id=d.user_id;
CREATE TABLE IF NOT EXISTS system_configuration (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assessments_session ON assessments(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_status ON sessions(user_id,status);
