ALTER TABLE training_activities ADD COLUMN posture_mode TEXT NOT NULL DEFAULT 'off';
ALTER TABLE training_activities ADD COLUMN knowledge_mode TEXT NOT NULL DEFAULT 'off';
ALTER TABLE sessions ADD COLUMN scenario_snapshot_json TEXT;
CREATE TABLE scenario_previews (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL, activity_id TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0
);
UPDATE training_activities SET posture_mode='optional' WHERE primary_skill_id IN ('presentations','interviews');
UPDATE training_activities SET knowledge_mode='optional' WHERE training_language IS NULL;
