import asyncio
import json
import sqlite3
from datetime import datetime
from typing import Any

from app.db.database import connect


VALID_STATUSES = {"unread", "read"}


def recommendation_title_key(title: str) -> str:
    return "".join(character for character in title.casefold() if character.isalnum())


def _clean_title(title: str) -> str:
    return str(title or "").strip()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in columns)


def _init_actionable_recommendation_db_sync() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS actionable_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                title_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unread',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                read_at TEXT,
                UNIQUE(user_id, title_key),
                CHECK(status IN ('unread', 'read'))
            )
            """
        )
        if not _has_column(conn, "actionable_recommendations", "payload"):
            conn.execute("ALTER TABLE actionable_recommendations ADD COLUMN payload TEXT")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_actionable_recommendations_user_status
            ON actionable_recommendations(user_id, status, updated_at)
            """
        )


async def init_actionable_recommendation_db() -> None:
    await asyncio.to_thread(_init_actionable_recommendation_db_sync)


def _row_to_recommendation(row) -> dict:
    return {
        "user_id": row["user_id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "read_at": row["read_at"],
    }


def _row_to_recommendation_payload(row) -> dict | None:
    payload = _json_load(row["payload"], None)
    if not isinstance(payload, dict):
        return None
    return payload


def _save_actionable_recommendation_titles_sync(
    *,
    user_id: str,
    titles: list[str],
) -> None:
    _init_actionable_recommendation_db_sync()
    now = datetime.utcnow().isoformat()

    with connect() as conn:
        for title in titles:
            clean_title = _clean_title(title)
            title_key = recommendation_title_key(clean_title)
            if not title_key:
                continue

            conn.execute(
                """
                INSERT INTO actionable_recommendations (
                    user_id, title, title_key, status, created_at, updated_at
                ) VALUES (?, ?, ?, 'unread', ?, ?)
                ON CONFLICT(user_id, title_key) DO UPDATE SET
                    title = excluded.title,
                    updated_at = excluded.updated_at
                """,
                (user_id, clean_title, title_key, now, now),
            )


def _save_actionable_recommendations_sync(
    *,
    user_id: str,
    recommendations: list[dict],
) -> int:
    _init_actionable_recommendation_db_sync()
    now = datetime.utcnow().isoformat()
    saved_count = 0

    with connect() as conn:
        for recommendation in recommendations:
            if not isinstance(recommendation, dict):
                continue

            clean_title = _clean_title(recommendation.get("title"))
            title_key = recommendation_title_key(clean_title)
            if not title_key:
                continue

            conn.execute(
                """
                INSERT INTO actionable_recommendations (
                    user_id, title, title_key, status, payload, created_at, updated_at
                ) VALUES (?, ?, ?, 'unread', ?, ?, ?)
                ON CONFLICT(user_id, title_key) DO UPDATE SET
                    title = excluded.title,
                    status = 'unread',
                    payload = excluded.payload,
                    updated_at = excluded.updated_at,
                    read_at = NULL
                """,
                (
                    user_id,
                    clean_title,
                    title_key,
                    _json_dump(recommendation),
                    now,
                    now,
                ),
            )
            saved_count += 1

    return saved_count


async def save_actionable_recommendation_titles(
    *,
    user_id: str,
    titles: list[str],
) -> None:
    await asyncio.to_thread(
        _save_actionable_recommendation_titles_sync,
        user_id=user_id,
        titles=titles,
    )


async def save_actionable_recommendations(
    *,
    user_id: str,
    recommendations: list[dict],
) -> int:
    return await asyncio.to_thread(
        _save_actionable_recommendations_sync,
        user_id=user_id,
        recommendations=recommendations,
    )


def _get_unread_actionable_recommendations_sync(user_id: str) -> list[dict]:
    _init_actionable_recommendation_db_sync()

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM actionable_recommendations
            WHERE user_id = ?
              AND status = 'unread'
              AND payload IS NOT NULL
            ORDER BY updated_at DESC, id ASC
            """,
            (user_id,),
        ).fetchall()

    return [
        payload
        for row in rows
        for payload in [_row_to_recommendation_payload(row)]
        if payload is not None
    ]


async def get_unread_actionable_recommendations(user_id: str) -> list[dict]:
    return await asyncio.to_thread(
        _get_unread_actionable_recommendations_sync,
        user_id,
    )


def _get_read_actionable_recommendation_title_keys_sync(user_id: str) -> set[str]:
    _init_actionable_recommendation_db_sync()

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT title_key
            FROM actionable_recommendations
            WHERE user_id = ? AND status = 'read'
            """,
            (user_id,),
        ).fetchall()

    return {row["title_key"] for row in rows}


async def get_read_actionable_recommendation_title_keys(user_id: str) -> set[str]:
    return await asyncio.to_thread(
        _get_read_actionable_recommendation_title_keys_sync,
        user_id,
    )


def _update_actionable_recommendation_status_sync(
    *,
    user_id: str,
    title: str,
    status: str,
) -> dict | None:
    if status not in VALID_STATUSES:
        raise ValueError("status must be read or unread.")

    _init_actionable_recommendation_db_sync()
    clean_title = _clean_title(title)
    title_key = recommendation_title_key(clean_title)
    if not title_key:
        raise ValueError("title is required.")

    now = datetime.utcnow().isoformat()
    read_at = now if status == "read" else None

    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM actionable_recommendations
            WHERE user_id = ? AND title_key = ?
            """,
            (user_id, title_key),
        ).fetchone()

        if not existing:
            return None

        conn.execute(
            """
            UPDATE actionable_recommendations
            SET status = ?,
                updated_at = ?,
                read_at = ?
            WHERE user_id = ? AND title_key = ?
            """,
            (status, now, read_at, user_id, title_key),
        )

        row = conn.execute(
            """
            SELECT *
            FROM actionable_recommendations
            WHERE user_id = ? AND title_key = ?
            """,
            (user_id, title_key),
        ).fetchone()

    return _row_to_recommendation(row) if row else None


async def update_actionable_recommendation_status(
    *,
    user_id: str,
    title: str,
    status: str,
) -> dict | None:
    return await asyncio.to_thread(
        _update_actionable_recommendation_status_sync,
        user_id=user_id,
        title=title,
        status=status,
    )
