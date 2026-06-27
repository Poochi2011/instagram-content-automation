"""SQLite connection management and schema initialization."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from utils.exceptions import DatabaseError
from utils.logger import get_logger

logger = get_logger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class Database:
    """Thin wrapper around a SQLite connection for one database file."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            try:
                self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
                self._connection.row_factory = sqlite3.Row
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute("PRAGMA busy_timeout = 5000")
            except sqlite3.Error as exc:
                raise DatabaseError(f"Failed to connect to database at {self.db_path}: {exc}") from exc
        return self._connection

    def initialize_schema(self) -> None:
        """Run schema.sql. Safe to call on every startup (CREATE TABLE IF NOT EXISTS)."""
        try:
            sql = SCHEMA_PATH.read_text(encoding="utf-8")
            self.connection.executescript(sql)
            self.connection.commit()
            logger.info("Database schema ready at %s", self.db_path)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to initialize schema: {exc}") from exc

    @contextmanager
    def cursor(self):
        """Context manager yielding a cursor, committing on success and rolling back on error."""
        cur = self.connection.cursor()
        try:
            yield cur
            self.connection.commit()
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise DatabaseError(str(exc)) from exc
        finally:
            cur.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
