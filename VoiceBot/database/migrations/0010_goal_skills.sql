ALTER TABLE user_goals ADD COLUMN skill_id TEXT REFERENCES skill_catalog(id);
