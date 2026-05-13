import asyncio
import json
import sqlite3
from datetime import datetime
from typing import Any

from app.db.database import connect


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in columns)


def _init_user_business_db_sync() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                context_id INTEGER NOT NULL,
                business_name TEXT NOT NULL,
                business_category TEXT,
                phone_no TEXT,
                website TEXT,
                business_address TEXT,
                input_address TEXT,
                place_id TEXT NOT NULL,
                place_payload TEXT NOT NULL,
                raw_input TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, place_id),
                FOREIGN KEY(context_id) REFERENCES business_contexts(id),
                FOREIGN KEY(place_id) REFERENCES places(place_id)
            )
            """
        )
        if not _has_column(conn, "user_businesses", "phone_no"):
            conn.execute("ALTER TABLE user_businesses ADD COLUMN phone_no TEXT")
        if not _has_column(conn, "user_businesses", "website"):
            conn.execute("ALTER TABLE user_businesses ADD COLUMN website TEXT")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_businesses_user
            ON user_businesses(user_id, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_businesses_context
            ON user_businesses(context_id)
            """
        )


async def init_user_business_db() -> None:
    await asyncio.to_thread(_init_user_business_db_sync)


def _row_to_business(row) -> dict:
    business = dict(row)
    business["place_payload"] = _json_load(business.get("place_payload"), {})
    business["raw_input"] = _json_load(business.get("raw_input"), {})
    return business


def _save_user_businesses_sync(
    *,
    context_id: int,
    user_id: str,
    businesses: list[dict],
) -> None:
    _init_user_business_db_sync()
    now = datetime.utcnow().isoformat()

    with connect() as conn:
        for business in businesses:
            existing = conn.execute(
                """
                SELECT id, created_at FROM user_businesses
                WHERE user_id = ? AND place_id = ?
                """,
                (user_id, business["place_id"]),
            ).fetchone()

            values = (
                context_id,
                business["business_name"],
                business.get("business_category"),
                business.get("phone_no"),
                business.get("website"),
                business.get("business_address"),
                business.get("input_address"),
                _json_dump(business.get("place_payload", {})),
                _json_dump(business.get("raw_input", {})),
                now,
                user_id,
                business["place_id"],
            )

            if existing:
                conn.execute(
                    """
                    UPDATE user_businesses
                    SET context_id = ?,
                        business_name = ?,
                        business_category = ?,
                        phone_no = ?,
                        website = ?,
                        business_address = ?,
                        input_address = ?,
                        place_payload = ?,
                        raw_input = ?,
                        updated_at = ?
                    WHERE user_id = ? AND place_id = ?
                    """,
                    values,
                )
                continue

            conn.execute(
                """
                INSERT INTO user_businesses (
                    user_id, context_id, business_name, business_category,
                    phone_no, website, business_address, input_address, place_id,
                    place_payload, raw_input, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    context_id,
                    business["business_name"],
                    business.get("business_category"),
                    business.get("phone_no"),
                    business.get("website"),
                    business.get("business_address"),
                    business.get("input_address"),
                    business["place_id"],
                    _json_dump(business.get("place_payload", {})),
                    _json_dump(business.get("raw_input", {})),
                    now,
                    now,
                ),
            )


async def save_user_businesses(
    *,
    context_id: int,
    user_id: str,
    businesses: list[dict],
) -> None:
    await asyncio.to_thread(
        _save_user_businesses_sync,
        context_id=context_id,
        user_id=user_id,
        businesses=businesses,
    )


def _get_user_businesses_sync(user_id: str) -> list[dict]:
    _init_user_business_db_sync()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM user_businesses
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()

    return [_row_to_business(row) for row in rows]


async def get_user_businesses(user_id: str) -> list[dict]:
    return await asyncio.to_thread(_get_user_businesses_sync, user_id)


def _get_all_user_businesses_sync() -> list[dict]:
    _init_user_business_db_sync()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM user_businesses
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()

    return [_row_to_business(row) for row in rows]


async def get_all_user_businesses() -> list[dict]:
    return await asyncio.to_thread(_get_all_user_businesses_sync)
