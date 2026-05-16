import asyncio
import json
import sqlite3
from datetime import datetime
from typing import Any

from app.db.database import connect
from app.utils.business_matching import business_matches


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
        if not _has_column(conn, "user_businesses", "account_status"):
            conn.execute(
                "ALTER TABLE user_businesses ADD COLUMN account_status TEXT NOT NULL DEFAULT 'active'"
            )
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
    business["account_status"] = business.get("account_status") or "active"
    business["is_suspended"] = business["account_status"] == "suspended"
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
              AND account_status != 'suspended'
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


def _normalize_business_name(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _update_business_account_status_sync(
    *,
    business_name: str,
    account_status: str,
) -> dict | None:
    _init_user_business_db_sync()
    normalized_name = _normalize_business_name(business_name)
    now = datetime.utcnow().isoformat()

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM user_businesses
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        matched_ids = [
            row["id"]
            for row in rows
            if _normalize_business_name(row["business_name"]) == normalized_name
        ]

        if not matched_ids:
            return None

        conn.executemany(
            """
            UPDATE user_businesses
            SET account_status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            [(account_status, now, business_id) for business_id in matched_ids],
        )

        placeholders = ",".join("?" for _ in matched_ids)
        updated_rows = conn.execute(
            f"""
            SELECT *
            FROM user_businesses
            WHERE id IN ({placeholders})
            ORDER BY updated_at DESC, id DESC
            """,
            matched_ids,
        ).fetchall()

    updated_businesses = [_row_to_business(row) for row in updated_rows]
    return {
        "business_name": updated_businesses[0].get("business_name"),
        "account_status": account_status,
        "is_suspended": account_status == "suspended",
        "updated_count": len(updated_businesses),
        "businesses": updated_businesses,
    }


async def update_business_account_status(
    *,
    business_name: str,
    account_status: str,
) -> dict | None:
    return await asyncio.to_thread(
        _update_business_account_status_sync,
        business_name=business_name,
        account_status=account_status,
    )





def _business_map_url(place_id: str | None) -> str | None:
    if not place_id:
        return None

    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"


def _business_profile_response(business: dict) -> dict:
    return {
        "business_name": business.get("business_name"),
        "category": business.get("business_category"),
        "location": business.get("business_address") or business.get("input_address"),
        "map_url": _business_map_url(business.get("place_id")),
        "phone_no": business.get("phone_no"),
        "website": business.get("website"),
    }


def _updated_profile_raw_input(
    raw_input: dict,
    *,
    business_name: str,
    category: str | None,
    location: str | None,
    phone_no: str | None,
    website: str | None,
) -> dict:
    updated_raw_input = dict(raw_input or {})
    raw_business = dict(updated_raw_input.get("business") or {})

    raw_business["name"] = business_name
    if category is not None:
        raw_business["category"] = category
    if phone_no is not None:
        raw_business["phone_no"] = phone_no
    if website is not None:
        raw_business["website"] = website

    raw_location = dict(updated_raw_input.get("location") or {})
    previous_google_maps_url = raw_location.get("google_maps_url")
    previous_address = raw_location.get("address_or_city")

    if location is not None:
        raw_location["address_or_city"] = location
        updated_raw_input["location"] = raw_location

        raw_locations = raw_business.get("locations")
        if isinstance(raw_locations, list):
            updated_locations = []
            for raw_location_item in raw_locations:
                if not isinstance(raw_location_item, dict):
                    updated_locations.append(raw_location_item)
                    continue

                updated_location_item = dict(raw_location_item)
                same_saved_location = (
                    previous_google_maps_url
                    and updated_location_item.get("google_maps_url")
                    == previous_google_maps_url
                ) or (
                    previous_address
                    and updated_location_item.get("address_or_city")
                    == previous_address
                )

                if same_saved_location:
                    updated_location_item["address_or_city"] = location

                updated_locations.append(updated_location_item)

            raw_business["locations"] = updated_locations

    updated_raw_input["business"] = raw_business
    return updated_raw_input


def _get_business_profile_sync(
    *,
    user_id: str,
    business_name: str,
    location: str,
) -> dict | None:
    _init_user_business_db_sync()

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM user_businesses
            WHERE user_id = ?
              AND account_status != 'suspended'
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()

    for row in rows:
        business = _row_to_business(row)

        if business_matches(
            business,
            business_name=business_name,
            address=location,
        ):
            return _business_profile_response(business)

    return None



#new code for business profile update and retrieval

async def get_business_profile(
    *,
    user_id: str,
    business_name: str,
    location: str,
) -> dict | None:
    return await asyncio.to_thread(
        _get_business_profile_sync,
        user_id=user_id,
        business_name=business_name,
        location=location,
    )


def _update_business_profile_sync(
    *,
    user_id: str,
    existing_business_name: str,
    existing_location: str,
    new_business_name: str | None,
    category: str | None,
    new_location: str | None,
    place_id: str | None,
    phone_no: str | None,
    website: str | None,
) -> dict | None:
    _init_user_business_db_sync()

    now = datetime.utcnow().isoformat()

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

        matched = None

        for row in rows:
            business = _row_to_business(row)

            if business_matches(
                business,
                business_name=existing_business_name,
                address=existing_location,
            ):
                matched = business
                break

        if not matched:
            return None

        current_location = matched.get("business_address") or matched.get("input_address")
        updated_business_name = (
            new_business_name
            if new_business_name is not None
            else matched.get("business_name")
        )
        updated_category = (
            category
            if category is not None
            else matched.get("business_category")
        )
        updated_location = (
            new_location
            if new_location is not None
            else current_location
        )
        updated_input_location = (
            new_location
            if new_location is not None
            else matched.get("input_address")
        )
        updated_phone_no = (
            phone_no
            if phone_no is not None
            else matched.get("phone_no")
        )
        updated_website = (
            website
            if website is not None
            else matched.get("website")
        )
        new_place_id = place_id or matched.get("place_id")
        updated_raw_input = _updated_profile_raw_input(
            matched.get("raw_input") or {},
            business_name=updated_business_name,
            category=updated_category,
            location=updated_location,
            phone_no=updated_phone_no,
            website=updated_website,
        )

        conn.execute(
            """
            UPDATE user_businesses
            SET business_name = ?,
                business_category = ?,
                business_address = ?,
                input_address = ?,
                place_id = ?,
                phone_no = ?,
                website = ?,
                raw_input = ?,
                updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                updated_business_name,
                updated_category,
                updated_location,
                updated_input_location,
                new_place_id,
                updated_phone_no,
                updated_website,
                _json_dump(updated_raw_input),
                now,
                matched["id"],
                user_id,
            ),
        )
        conn.execute(
            """
            UPDATE business_contexts
            SET business_name = ?,
                business_category = ?,
                business_address = ?,
                primary_place_id = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                updated_business_name,
                updated_category,
                updated_location,
                new_place_id,
                matched["context_id"],
                user_id,
            ),
        )

        updated = conn.execute(
            """
            SELECT *
            FROM user_businesses
            WHERE id = ? AND user_id = ?
            """,
            (matched["id"], user_id),
        ).fetchone()

    if not updated:
        return None

    return _business_profile_response(_row_to_business(updated))


async def update_business_profile(
    *,
    user_id: str,
    existing_business_name: str,
    existing_location: str,
    new_business_name: str | None = None,
    category: str | None = None,
    new_location: str | None = None,
    place_id: str | None = None,
    phone_no: str | None = None,
    website: str | None = None,
) -> dict | None:
    return await asyncio.to_thread(
        _update_business_profile_sync,
        user_id=user_id,
        existing_business_name=existing_business_name,
        existing_location=existing_location,
        new_business_name=new_business_name,
        category=category,
        new_location=new_location,
        place_id=place_id,
        phone_no=phone_no,
        website=website,
    )
