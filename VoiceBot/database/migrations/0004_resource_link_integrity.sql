-- Make skill-level resource links idempotent even when subskill_id is NULL.
DELETE FROM resource_skill_links
WHERE rowid NOT IN (
    SELECT MIN(rowid) FROM resource_skill_links
    GROUP BY resource_id, skill_id, COALESCE(subskill_id, '')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_resource_skill_unique
ON resource_skill_links(resource_id, skill_id, COALESCE(subskill_id, ''));
