CREATE TABLE IF NOT EXISTS organization_invites (
    code_hash TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    used_at TEXT
);

-- SQLite cannot alter a CHECK constraint, so the table is rebuilt to allow trainers.
CREATE TABLE organization_memberships_new (
    organization_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('owner','admin','trainer','learner')),
    created_at TEXT NOT NULL,
    PRIMARY KEY(organization_id, user_id),
    FOREIGN KEY(organization_id) REFERENCES organizations(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
INSERT INTO organization_memberships_new(organization_id,user_id,role,created_at)
    SELECT organization_id,user_id,role,created_at FROM organization_memberships;
DROP TABLE organization_memberships;
ALTER TABLE organization_memberships_new RENAME TO organization_memberships;
