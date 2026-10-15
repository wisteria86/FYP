-- Language curriculum metadata, native-language captions, and attributed AI turns.
ALTER TABLE user_settings ADD COLUMN native_language TEXT NOT NULL DEFAULT 'Urdu';
ALTER TABLE user_settings ADD COLUMN proficiency_level TEXT NOT NULL DEFAULT 'beginner';

ALTER TABLE training_activities ADD COLUMN training_language TEXT;
ALTER TABLE training_activities ADD COLUMN proficiency_level TEXT;
ALTER TABLE training_activities ADD COLUMN sequence_number INTEGER;
ALTER TABLE training_activities ADD COLUMN roleplay_mode TEXT NOT NULL DEFAULT 'one_to_one';

ALTER TABLE sessions ADD COLUMN activity_id TEXT;
ALTER TABLE turns ADD COLUMN speaker_name TEXT;
ALTER TABLE turns ADD COLUMN caption_text TEXT;

CREATE INDEX IF NOT EXISTS idx_activities_language_sequence
ON training_activities(training_language, sequence_number);

