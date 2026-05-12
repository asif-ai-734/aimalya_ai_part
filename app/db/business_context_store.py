import asyncio
import json
import sqlite3
from datetime import datetime
from typing import Any

from app.db.database import connect


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in columns)


def _init_business_context_sync() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS business_contexts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                primary_place_id TEXT NOT NULL,
                place_ids TEXT NOT NULL,
                competitor_place_ids TEXT NOT NULL,
                business_name TEXT,
                business_address TEXT,
                business_category TEXT,
                report_frequency TEXT,
                goals TEXT NOT NULL,
                raw_input TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        if not _has_column(conn, "business_contexts", "user_id"):
            conn.execute("ALTER TABLE business_contexts ADD COLUMN user_id TEXT")
        if not _has_column(conn, "business_contexts", "business_address"):
            conn.execute(
                "ALTER TABLE business_contexts ADD COLUMN business_address TEXT"
            )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_business_contexts_user_created
            ON business_contexts(user_id, created_at, id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_business_contexts_primary_place
            ON business_contexts(primary_place_id)
            """
        )


async def init_business_context_db() -> None:
    await asyncio.to_thread(_init_business_context_sync)


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _save_business_context_sync(
    *,
    user_id: str | None,
    primary_place_id: str,
    place_ids: list[str],
    competitor_place_ids: list[str],
    business_name: str | None,
    business_address: str | None,
    business_category: str | None,
    report_frequency: str | None,
    goals: list[str],
    raw_input: dict,
) -> int:
    _init_business_context_sync()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO business_contexts (
                user_id, primary_place_id, place_ids, competitor_place_ids,
                business_name, business_address, business_category, report_frequency,
                goals, raw_input, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                primary_place_id,
                _json_dump(place_ids),
                _json_dump(competitor_place_ids),
                business_name,
                business_address,
                business_category,
                report_frequency,
                _json_dump(goals),
                _json_dump(raw_input),
                datetime.utcnow().isoformat(),
            ),
        )
        return int(cursor.lastrowid)


async def save_business_context(
    *,
    user_id: str | None,
    primary_place_id: str,
    place_ids: list[str],
    competitor_place_ids: list[str],
    business_name: str | None,
    business_address: str | None,
    business_category: str | None,
    report_frequency: str | None,
    goals: list[str],
    raw_input: dict,
) -> int:
    return await asyncio.to_thread(
        _save_business_context_sync,
        user_id=user_id,
        primary_place_id=primary_place_id,
        place_ids=place_ids,
        competitor_place_ids=competitor_place_ids,
        business_name=business_name,
        business_address=business_address,
        business_category=business_category,
        report_frequency=report_frequency,
        goals=goals,
        raw_input=raw_input,
    )


def _row_to_context(row: sqlite3.Row) -> dict:
    context = dict(row)
    context["place_ids"] = _json_load(context.get("place_ids"), [])
    context["competitor_place_ids"] = _json_load(
        context.get("competitor_place_ids"), []
    )
    context["goals"] = _json_load(context.get("goals"), [])
    context["raw_input"] = _json_load(context.get("raw_input"), {})
    return context


def _business_name_matches(context: dict, business_name: str) -> bool:
    requested_name = business_name.strip().casefold()
    if not requested_name:
        return False

    stored_name = (context.get("business_name") or "").strip().casefold()
    if stored_name == requested_name:
        return True

    raw_input = context.get("raw_input", {})
    business_setup = raw_input.get("business_setup", raw_input)
    for business in business_setup.get("businesses", []):
        name = (business.get("name") or "").strip().casefold()
        if name == requested_name:
            return True

    return False


def _get_latest_business_context_sync(
    place_id: str | None = None,
    user_id: str | None = None,
) -> dict | None:
    _init_business_context_sync()
    with connect() as conn:
        if place_id:
            rows = conn.execute(
                """
                SELECT * FROM business_contexts
                WHERE (? IS NULL OR user_id = ?)
                ORDER BY created_at DESC, id DESC
                """,
                (user_id, user_id),
            ).fetchall()
            for row in rows:
                context = _row_to_context(row)
                if (
                    context["primary_place_id"] == place_id
                    or place_id in context["place_ids"]
                ):
                    return context
            return None

        row = conn.execute(
            """
            SELECT * FROM business_contexts
            WHERE (? IS NULL OR user_id = ?)
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (user_id, user_id),
        ).fetchone()

    return _row_to_context(row) if row else None


async def get_latest_business_context(
    place_id: str | None = None,
    user_id: str | None = None,
) -> dict | None:
    return await asyncio.to_thread(
        _get_latest_business_context_sync,
        place_id,
        user_id,
    )


def _get_latest_business_context_by_name_sync(
    business_name: str,
    user_id: str | None = None,
) -> dict | None:
    _init_business_context_sync()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM business_contexts
            WHERE (? IS NULL OR user_id = ?)
            ORDER BY created_at DESC, id DESC
            """,
            (user_id, user_id),
        ).fetchall()

    for row in rows:
        context = _row_to_context(row)
        if _business_name_matches(context, business_name):
            return context

    return None


async def get_latest_business_context_by_name(
    business_name: str,
    user_id: str | None = None,
) -> dict | None:
    return await asyncio.to_thread(
        _get_latest_business_context_by_name_sync,
        business_name,
        user_id,
    )


def _merge_goal_raw_input(current_raw_input: dict, goals_input: dict) -> dict:
    business_setup = current_raw_input.get("business_setup", current_raw_input)
    return {
        "business_setup": business_setup,
        "goals_setup": goals_input,
    }


def _update_business_context_goals_sync(
    *,
    context_id: int,
    competitor_place_ids: list[str],
    goals: list[str],
    goals_input: dict,
) -> dict | None:
    _init_business_context_sync()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM business_contexts WHERE id = ?",
            (context_id,),
        ).fetchone()
        if not row:
            return None

        context = _row_to_context(row)
        merged_raw_input = _merge_goal_raw_input(
            context.get("raw_input", {}),
            goals_input,
        )

        conn.execute(
            """
            UPDATE business_contexts
            SET competitor_place_ids = ?,
                goals = ?,
                raw_input = ?
            WHERE id = ?
            """,
            (
                _json_dump(competitor_place_ids),
                _json_dump(goals),
                _json_dump(merged_raw_input),
                context_id,
            ),
        )

        updated_row = conn.execute(
            "SELECT * FROM business_contexts WHERE id = ?",
            (context_id,),
        ).fetchone()

    return _row_to_context(updated_row) if updated_row else None


async def update_business_context_goals(
    *,
    context_id: int,
    competitor_place_ids: list[str],
    goals: list[str],
    goals_input: dict,
) -> dict | None:
    return await asyncio.to_thread(
        _update_business_context_goals_sync,
        context_id=context_id,
        competitor_place_ids=competitor_place_ids,
        goals=goals,
        goals_input=goals_input,
    )
