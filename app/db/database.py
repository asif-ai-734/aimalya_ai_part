import sqlite3
from pathlib import Path

from app.core.config import get_settings


settings = get_settings()


def _ensure_db_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    _ensure_db_dir(settings.DB_PATH)
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
