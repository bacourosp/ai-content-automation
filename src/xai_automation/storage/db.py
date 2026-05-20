from __future__ import annotations

import sqlite3
from pathlib import Path

from xai_automation.storage.schema import SCHEMA_SQL


class Database:
    def __init__(self, sqlite_path: Path):
        self._path = sqlite_path

    @property
    def path(self) -> Path:
        return self._path

    def connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self._path)
        con.row_factory = sqlite3.Row
        return con

    def init(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA_SQL)
            con.commit()
