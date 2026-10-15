"""Small, dependency-free migration runner for the local Hikari deployment."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from database.connection import connect_database


MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def _migration_files() -> list[tuple[int, Path]]:
    migrations: list[tuple[int, Path]] = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        match = MIGRATION_NAME.match(path.name)
        if match:
            migrations.append((int(match.group(1)), path))
    return sorted(migrations)


def current_version(database_path: str | Path) -> int:
    with connect_database(database_path) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        row = db.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        return int(row["version"] or 0)


def run_migrations(database_path: str | Path) -> list[int]:
    """Apply every pending SQL migration exactly once and return applied versions."""

    applied: list[int] = []
    with connect_database(database_path) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        completed = {row["version"] for row in db.execute("SELECT version FROM schema_migrations")}
        for version, path in _migration_files():
            if version in completed:
                continue
            db.executescript(path.read_text(encoding="utf-8"))
            db.execute(
                "INSERT INTO schema_migrations(version,name,applied_at) VALUES (?,?,?)",
                (version, path.name, datetime.now(timezone.utc).isoformat()),
            )
            applied.append(version)
    return applied
