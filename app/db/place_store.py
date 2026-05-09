import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any

from app.db.database import connect


def _init_place_db_sync() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS places (
                place_id TEXT PRIMARY KEY,
                name TEXT,
                business_status TEXT,
                types TEXT,
                formatted_address TEXT,
                rating REAL,
                user_ratings_total INTEGER,
                price_level INTEGER,
                opening_hours_open_now INTEGER,
                opening_hours_weekday_text TEXT,
                formatted_phone_number TEXT,
                international_phone_number TEXT,
                website TEXT,
                geometry_location_lat REAL,
                geometry_location_lng REAL,
                geometry_viewport_ne_lat REAL,
                geometry_viewport_ne_lng REAL,
                geometry_viewport_sw_lat REAL,
                geometry_viewport_sw_lng REAL,
                wheelchair_accessible_entrance INTEGER,
                serves_vegetarian_food INTEGER,
                takeout INTEGER,
                dine_in INTEGER,
                delivery INTEGER,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                place_id TEXT NOT NULL,
                height INTEGER,
                width INTEGER,
                photo_reference TEXT UNIQUE,
                html_attributions TEXT,
                FOREIGN KEY(place_id) REFERENCES places(place_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                place_id TEXT NOT NULL,
                author_name TEXT,
                rating INTEGER,
                text TEXT,
                time INTEGER,
                relative_time_description TEXT,
                language TEXT,
                review_hash TEXT UNIQUE,
                FOREIGN KEY(place_id) REFERENCES places(place_id)
            )
            """
        )


async def init_place_db() -> None:
    await asyncio.to_thread(_init_place_db_sync)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(bool(value))


def _make_review_hash(place_id: str, review: dict) -> str:
    raw = f"{place_id}|{review.get('author_name','')}|{review.get('time','')}|{review.get('text','')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _upsert_place_data_sync(place: dict) -> None:
    _init_place_db_sync()
    place_id = place.get("place_id")
    if not place_id:
        return

    geometry = place.get("geometry", {})
    location = geometry.get("location", {})
    viewport = geometry.get("viewport", {})
    ne = viewport.get("northeast", {})
    sw = viewport.get("southwest", {})

    opening_hours = place.get("opening_hours", {})

    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO places (
                place_id, name, business_status, types, formatted_address,
                rating, user_ratings_total, price_level,
                opening_hours_open_now, opening_hours_weekday_text,
                formatted_phone_number, international_phone_number, website,
                geometry_location_lat, geometry_location_lng,
                geometry_viewport_ne_lat, geometry_viewport_ne_lng,
                geometry_viewport_sw_lat, geometry_viewport_sw_lng,
                wheelchair_accessible_entrance, serves_vegetarian_food,
                takeout, dine_in, delivery, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                place_id,
                place.get("name"),
                place.get("business_status"),
                json.dumps(place.get("types", []), ensure_ascii=True),
                place.get("formatted_address"),
                place.get("rating"),
                place.get("user_ratings_total"),
                place.get("price_level"),
                _to_int(opening_hours.get("open_now")),
                json.dumps(opening_hours.get("weekday_text", []), ensure_ascii=True),
                place.get("formatted_phone_number"),
                place.get("international_phone_number"),
                place.get("website"),
                location.get("lat"),
                location.get("lng"),
                ne.get("lat"),
                ne.get("lng"),
                sw.get("lat"),
                sw.get("lng"),
                _to_int(place.get("wheelchair_accessible_entrance")),
                _to_int(place.get("serves_vegetarian_food")),
                _to_int(place.get("takeout")),
                _to_int(place.get("dine_in")),
                _to_int(place.get("delivery")),
                datetime.utcnow().isoformat(),
            ),
        )

        for photo in place.get("photos", []):
            conn.execute(
                """
                INSERT OR IGNORE INTO photos (
                    place_id, height, width, photo_reference, html_attributions
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    place_id,
                    photo.get("height"),
                    photo.get("width"),
                    photo.get("photo_reference"),
                    json.dumps(photo.get("html_attributions", []), ensure_ascii=True),
                ),
            )

        for review in place.get("reviews", []):
            review_hash = _make_review_hash(place_id, review)
            conn.execute(
                """
                INSERT OR IGNORE INTO reviews (
                    place_id, author_name, rating, text, time,
                    relative_time_description, language, review_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    place_id,
                    review.get("author_name"),
                    review.get("rating"),
                    review.get("text"),
                    review.get("time"),
                    review.get("relative_time_description"),
                    review.get("language"),
                    review_hash,
                ),
            )


async def upsert_place_data(place: dict) -> None:
    await asyncio.to_thread(_upsert_place_data_sync, place)


def _get_place_data_sync(place_id: str | None = None) -> dict | None:
    _init_place_db_sync()
    with connect() as conn:
        if place_id:
            place_row = conn.execute(
                "SELECT * FROM places WHERE place_id = ?",
                (place_id,),
            ).fetchone()
        else:
            place_row = conn.execute(
                "SELECT * FROM places ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()

        if not place_row:
            return None

        pid = place_row["place_id"]

        photo_rows = conn.execute(
            "SELECT * FROM photos WHERE place_id = ? ORDER BY id",
            (pid,),
        ).fetchall()
        review_rows = conn.execute(
            "SELECT * FROM reviews WHERE place_id = ? ORDER BY time DESC",
            (pid,),
        ).fetchall()

    place = dict(place_row)
    place["types"] = json.loads(place.get("types") or "[]")
    place["opening_hours"] = {
        "open_now": bool(place.get("opening_hours_open_now"))
        if place.get("opening_hours_open_now") is not None
        else None,
        "weekday_text": json.loads(place.get("opening_hours_weekday_text") or "[]"),
    }
    place["geometry"] = {
        "location": {
            "lat": place.get("geometry_location_lat"),
            "lng": place.get("geometry_location_lng"),
        },
        "viewport": {
            "northeast": {
                "lat": place.get("geometry_viewport_ne_lat"),
                "lng": place.get("geometry_viewport_ne_lng"),
            },
            "southwest": {
                "lat": place.get("geometry_viewport_sw_lat"),
                "lng": place.get("geometry_viewport_sw_lng"),
            },
        },
    }
    place["wheelchair_accessible_entrance"] = bool(
        place.get("wheelchair_accessible_entrance")
    )
    place["serves_vegetarian_food"] = bool(place.get("serves_vegetarian_food"))
    place["takeout"] = bool(place.get("takeout"))
    place["dine_in"] = bool(place.get("dine_in"))
    place["delivery"] = bool(place.get("delivery"))

    place["photos"] = [
        {
            "height": r["height"],
            "width": r["width"],
            "photo_reference": r["photo_reference"],
            "html_attributions": json.loads(r["html_attributions"] or "[]"),
        }
        for r in photo_rows
    ]

    place["reviews"] = [
        {
            "author_name": r["author_name"],
            "rating": r["rating"],
            "text": r["text"],
            "time": r["time"],
            "relative_time_description": r["relative_time_description"],
            "language": r["language"],
        }
        for r in review_rows
    ]

    return place


async def get_place_data(place_id: str | None = None) -> dict | None:
    return await asyncio.to_thread(_get_place_data_sync, place_id)
