import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings


settings = get_settings()


def _ensure_db_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    _ensure_db_dir(settings.DB_PATH)
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_business_context_sync() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS business_contexts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                primary_place_id TEXT NOT NULL,
                place_ids TEXT NOT NULL,
                competitor_place_ids TEXT NOT NULL,
                business_name TEXT,
                business_category TEXT,
                report_frequency TEXT,
                goals TEXT NOT NULL,
                raw_input TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
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
    primary_place_id: str,
    place_ids: list[str],
    competitor_place_ids: list[str],
    business_name: str | None,
    business_category: str | None,
    report_frequency: str | None,
    goals: list[str],
    raw_input: dict,
) -> int:
    _init_business_context_sync()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO business_contexts (
                primary_place_id, place_ids, competitor_place_ids,
                business_name, business_category, report_frequency,
                goals, raw_input, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                primary_place_id,
                _json_dump(place_ids),
                _json_dump(competitor_place_ids),
                business_name,
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
    primary_place_id: str,
    place_ids: list[str],
    competitor_place_ids: list[str],
    business_name: str | None,
    business_category: str | None,
    report_frequency: str | None,
    goals: list[str],
    raw_input: dict,
) -> int:
    return await asyncio.to_thread(
        _save_business_context_sync,
        primary_place_id=primary_place_id,
        place_ids=place_ids,
        competitor_place_ids=competitor_place_ids,
        business_name=business_name,
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


def _get_latest_business_context_sync(place_id: str | None = None) -> dict | None:
    _init_business_context_sync()
    with _connect() as conn:
        if place_id:
            rows = conn.execute(
                """
                SELECT * FROM business_contexts
                ORDER BY created_at DESC, id DESC
                """
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
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()

    return _row_to_context(row) if row else None


async def get_latest_business_context(
    place_id: str | None = None,
) -> dict | None:
    return await asyncio.to_thread(_get_latest_business_context_sync, place_id)


def _get_latest_business_context_by_name_sync(
    business_name: str,
) -> dict | None:
    _init_business_context_sync()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM business_contexts
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    for row in rows:
        context = _row_to_context(row)
        if _business_name_matches(context, business_name):
            return context

    return None


async def get_latest_business_context_by_name(
    business_name: str,
) -> dict | None:
    return await asyncio.to_thread(
        _get_latest_business_context_by_name_sync,
        business_name,
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
    report_frequency: str,
    goals: list[str],
    goals_input: dict,
) -> dict | None:
    _init_business_context_sync()
    with _connect() as conn:
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
                report_frequency = ?,
                goals = ?,
                raw_input = ?
            WHERE id = ?
            """,
            (
                _json_dump(competitor_place_ids),
                report_frequency,
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
    report_frequency: str,
    goals: list[str],
    goals_input: dict,
) -> dict | None:
    return await asyncio.to_thread(
        _update_business_context_goals_sync,
        context_id=context_id,
        competitor_place_ids=competitor_place_ids,
        report_frequency=report_frequency,
        goals=goals,
        goals_input=goals_input,
    )
