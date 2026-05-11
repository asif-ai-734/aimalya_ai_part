import asyncio
from typing import Any

from app.db.business_store import get_user_businesses
from app.db.place_store import get_place_data


def _first_truthy(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", []):
            return value
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _weighted_rating(ratings: list[tuple[float | None, int]]) -> float:
    valid = [(rating, reviews) for rating, reviews in ratings if rating is not None]
    if not valid:
        return 0.0

    weighted = [(rating, reviews) for rating, reviews in valid if reviews > 0]
    if weighted:
        review_total = sum(reviews for _, reviews in weighted)
        if review_total:
            return round(
                sum(rating * reviews for rating, reviews in weighted) / review_total,
                1,
            )

    return round(sum(rating for rating, _ in valid) / len(valid), 1)


def _rating_stars(rating: float | None) -> dict:
    value = max(0.0, min(float(rating or 0), 5.0))
    full = int(value)
    fraction = value - full

    if fraction >= 0.75 and full < 5:
        full += 1
        half = False
    else:
        half = fraction >= 0.25 and full < 5

    empty = max(5 - full - (1 if half else 0), 0)
    return {"full": full, "half": half, "empty": empty}


def _status_from_google_status(status: str | None) -> str:
    status = (status or "").upper()
    if status == "OPERATIONAL":
        return "active"
    if status == "CLOSED_TEMPORARILY":
        return "temporarily_closed"
    if status == "CLOSED_PERMANENTLY":
        return "closed"
    return "unknown"


def _group_status(locations: list[dict]) -> str:
    statuses = [location["status"] for location in locations]
    if "active" in statuses:
        return "active"
    if "temporarily_closed" in statuses:
        return "temporarily_closed"
    if "closed" in statuses:
        return "closed"
    return "unknown"


def _first_photo(place: dict) -> dict | None:
    photos = place.get("photos") or []
    if not photos:
        return None

    photo = photos[0]
    return {
        "photo_reference": photo.get("photo_reference"),
        "width": photo.get("width"),
        "height": photo.get("height"),
        "html_attributions": photo.get("html_attributions") or [],
    }


def _location_coordinates(place: dict) -> dict | None:
    location = (place.get("geometry") or {}).get("location") or {}
    lat = location.get("lat")
    lng = location.get("lng")
    if lat is None or lng is None:
        return None
    return {"lat": lat, "lng": lng}


def _recent_reviews(place: dict, *, limit: int = 5) -> list[dict]:
    reviews = sorted(
        place.get("reviews") or [],
        key=lambda review: review.get("time") or 0,
        reverse=True,
    )
    return [
        {
            "author_name": review.get("author_name"),
            "rating": review.get("rating"),
            "text": review.get("text"),
            "time": review.get("time"),
            "relative_time_description": review.get("relative_time_description"),
            "language": review.get("language"),
        }
        for review in reviews[:limit]
    ]


async def _place_for_business(business: dict) -> dict:
    place_id = business.get("place_id")
    place = await get_place_data(place_id) if place_id else None
    return place or business.get("place_payload") or {}


def _build_location(business: dict, place: dict) -> dict:
    opening_hours = place.get("opening_hours") or {}
    place_id = business.get("place_id")
    rating = _as_float(place.get("rating"))
    reviews = _as_int(place.get("user_ratings_total"))

    return {
        "id": business.get("id"),
        "context_id": business.get("context_id"),
        "place_id": place_id,
        "business_name": _first_truthy(
            business.get("business_name"),
            place.get("name"),
        ),
        "google_name": place.get("name"),
        "category": _first_truthy(
            business.get("business_category"),
            (place.get("types") or [None])[0],
        ),
        "address": _first_truthy(
            business.get("business_address"),
            place.get("formatted_address"),
            business.get("input_address"),
        ),
        "input_address": business.get("input_address"),
        "business_status": place.get("business_status"),
        "status": _status_from_google_status(place.get("business_status")),
        "open_now": opening_hours.get("open_now"),
        "rating": rating,
        "rating_stars": _rating_stars(rating),
        "reviews": reviews,
        "phone": _first_truthy(
            place.get("formatted_phone_number"),
            place.get("international_phone_number"),
        ),
        "website": place.get("website"),
        "price_level": place.get("price_level"),
        "coordinates": _location_coordinates(place),
        "photo": _first_photo(place),
        "google_maps_url": (
            f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            if place_id
            else None
        ),
        "recent_reviews": _recent_reviews(place),
        "created_at": business.get("created_at"),
        "updated_at": business.get("updated_at"),
    }


def _business_key(location: dict) -> str:
    name = (location.get("business_name") or "").strip().casefold()
    category = (location.get("category") or "").strip().casefold()
    return f"{name}|{category}"


def _build_summary_cards(summary: dict) -> list[dict]:
    return [
        {
            "key": "total_businesses",
            "label": "Total Businesses",
            "value": summary["total_businesses"],
            "change": None,
            "change_label": "vs last month",
        },
        {
            "key": "total_locations",
            "label": "Total Locations",
            "value": summary["total_locations"],
            "subtitle": "used for business",
        },
        {
            "key": "avg_rating",
            "label": "Avg Rating",
            "value": summary["avg_rating"],
            "rating_stars": _rating_stars(summary["avg_rating"]),
        },
        {
            "key": "total_reviews",
            "label": "Total Reviews",
            "value": summary["total_reviews"],
            "change": None,
            "change_label": "vs last month",
        },
    ]


def _build_location_filters(locations: list[dict]) -> list[dict]:
    filters = [{"label": "All locations", "value": "all"}]
    filters.extend(
        {
            "label": location.get("address") or location.get("google_name"),
            "value": location.get("place_id"),
        }
        for location in locations
        if location.get("place_id")
    )
    return filters


async def build_business_management(user_id: str) -> dict:
    user_businesses = await get_user_businesses(user_id)
    places = await asyncio.gather(
        *(_place_for_business(business) for business in user_businesses)
    )
    locations = [
        _build_location(business, place)
        for business, place in zip(user_businesses, places)
    ]

    grouped: dict[str, dict] = {}
    for location in locations:
        key = _business_key(location)
        group = grouped.setdefault(
            key,
            {
                "business_id": location.get("id"),
                "context_id": location.get("context_id"),
                "business_name": location.get("business_name"),
                "category": location.get("category"),
                "owner_id": user_id,
                "owner_name": None,
                "locations": [],
                "_ratings": [],
            },
        )
        group["locations"].append(location)
        group["_ratings"].append((location.get("rating"), location.get("reviews", 0)))

    businesses = []
    for group in grouped.values():
        group_locations = group["locations"]
        reviews = sum(location.get("reviews", 0) for location in group_locations)
        rating = _weighted_rating(group["_ratings"])
        recent_reviews = sorted(
            [
                review
                for location in group_locations
                for review in location.get("recent_reviews", [])
            ],
            key=lambda review: review.get("time") or 0,
            reverse=True,
        )[:5]

        businesses.append(
            {
                "business_id": group["business_id"],
                "context_id": group["context_id"],
                "business_name": group["business_name"],
                "category": group["category"],
                "owner_id": group["owner_id"],
                "owner_name": group["owner_name"],
                "status": _group_status(group_locations),
                "location_count": len(group_locations),
                "reviews": reviews,
                "rating": rating,
                "rating_stars": _rating_stars(rating),
                "primary_photo": next(
                    (
                        location.get("photo")
                        for location in group_locations
                        if location.get("photo")
                    ),
                    None,
                ),
                "primary_address": next(
                    (
                        location.get("address")
                        for location in group_locations
                        if location.get("address")
                    ),
                    None,
                ),
                "website": next(
                    (
                        location.get("website")
                        for location in group_locations
                        if location.get("website")
                    ),
                    None,
                ),
                "phone": next(
                    (
                        location.get("phone")
                        for location in group_locations
                        if location.get("phone")
                    ),
                    None,
                ),
                "recent_reviews": recent_reviews,
                "locations": group_locations,
            }
        )

    total_reviews = sum(location.get("reviews", 0) for location in locations)
    avg_rating = _weighted_rating(
        [(location.get("rating"), location.get("reviews", 0)) for location in locations]
    )
    summary = {
        "total_businesses": len(businesses),
        "total_locations": len(locations),
        "avg_rating": avg_rating,
        "total_reviews": total_reviews,
    }

    return {
        "user_id": user_id,
        "summary": summary,
        "summary_cards": _build_summary_cards(summary),
        "filters": {"locations": _build_location_filters(locations)},
        "businesses": businesses,
        "locations": locations,
        "trend_note": "Monthly comparison values are null because historical snapshots are not stored yet.",
    }
