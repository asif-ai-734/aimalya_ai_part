import asyncio
import sqlite3
from datetime import datetime

from app.db.database import connect


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in columns)

def _init_route_hit_db_sync() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS route_hits (
                user_id TEXT NOT NULL,
                route_path TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0,
                last_hit_at TEXT,
                PRIMARY KEY (user_id, route_path)
            )
            """
        )
        if not _has_column(conn, "route_hits", "last_hit_at"):
            conn.execute("ALTER TABLE route_hits ADD COLUMN last_hit_at TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS route_hit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                route_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_route_hit_events_user_route
            ON route_hit_events(user_id, route_path, created_at)
            """
        )

async def init_route_hit_db() -> None:
    await asyncio.to_thread(_init_route_hit_db_sync)

def _increment_and_get_hit_count_sync(user_id: str, route_path: str) -> int:
    _init_route_hit_db_sync()
    now = datetime.utcnow().isoformat()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO route_hits (user_id, route_path, hit_count, last_hit_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, route_path) DO UPDATE SET
                hit_count = hit_count + 1,
                last_hit_at = excluded.last_hit_at
            """,
            (user_id, route_path, now),
        )
        row = conn.execute(
            "SELECT hit_count FROM route_hits WHERE user_id = ? AND route_path = ?",
            (user_id, route_path),
        ).fetchone()
        return row["hit_count"] if row else 0

async def increment_and_get_hit_count(user_id: str, route_path: str) -> int:
    return await asyncio.to_thread(_increment_and_get_hit_count_sync, user_id, route_path)


def _record_route_event_sync(user_id: str, route_path: str) -> None:
    _init_route_hit_db_sync()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO route_hit_events (user_id, route_path, created_at)
            VALUES (?, ?, ?)
            """,
            (user_id, route_path, datetime.utcnow().isoformat()),
        )


async def record_route_event(user_id: str, route_path: str) -> None:
    await asyncio.to_thread(_record_route_event_sync, user_id, route_path)


def _get_recent_route_events_sync(
    user_id: str,
    route_paths: list[str],
    *,
    limit: int,
) -> list[dict]:
    _init_route_hit_db_sync()
    if not route_paths:
        return []

    placeholders = ",".join("?" for _ in route_paths)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT user_id, route_path, created_at
            FROM route_hit_events
            WHERE user_id = ?
              AND route_path IN ({placeholders})
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            [user_id, *route_paths, limit],
        ).fetchall()

    return [dict(row) for row in rows]


async def get_recent_route_events(
    user_id: str,
    route_paths: list[str],
    *,
    limit: int = 10,
) -> list[dict]:
    return await asyncio.to_thread(
        _get_recent_route_events_sync,
        user_id,
        route_paths,
        limit=limit,
    )
