"""Transactional storage boundary for application training services."""
from pathlib import Path
from database.connection import connect_database


class SqliteTrainingRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self):
        return connect_database(self.path)
