import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from core.training_service import TrainingService
from database.migration_runner import current_version, run_migrations


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "hikari.db"

    def tearDown(self):
        self.temp.cleanup()

    def test_new_database_reaches_platform_schema(self):
        TrainingService(self.path)
        self.assertEqual(current_version(self.path), 7)
        with closing(sqlite3.connect(self.path)) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({
                "organizations", "skill_catalog", "subskill_catalog",
                "training_activities", "scenario_templates", "proficiency_history",
                "training_plans", "recommendations", "resources", "document_chunks",
                "auth_sessions",
            }.issubset(tables))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM skill_catalog").fetchone()[0], 13)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM scenario_templates").fetchone()[0], 42)

    def test_migrations_are_idempotent(self):
        TrainingService(self.path)
        self.assertEqual(run_migrations(self.path), [])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 7)


if __name__ == "__main__":
    unittest.main()
