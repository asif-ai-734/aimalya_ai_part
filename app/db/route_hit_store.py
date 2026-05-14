import asyncio
from app.db.database import connect

def _init_route_hit_db_sync() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS route_hits (
                user_id TEXT NOT NULL,
                route_path TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, route_path)
            )
            """
        )

async def init_route_hit_db() -> None:
    await asyncio.to_thread(_init_route_hit_db_sync)

def _increment_and_get_hit_count_sync(user_id: str, route_path: str) -> int:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO route_hits (user_id, route_path, hit_count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, route_path) DO UPDATE SET
                hit_count = hit_count + 1
            """,
            (user_id, route_path),
        )
        row = conn.execute(
            "SELECT hit_count FROM route_hits WHERE user_id = ? AND route_path = ?",
            (user_id, route_path),
        ).fetchone()
        return row["hit_count"] if row else 0

async def increment_and_get_hit_count(user_id: str, route_path: str) -> int:
    return await asyncio.to_thread(_increment_and_get_hit_count_sync, user_id, route_path)
