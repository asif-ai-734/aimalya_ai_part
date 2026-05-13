import asyncio
from collections import Counter
from datetime import datetime, timedelta
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


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


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


def _all_reviews(place: dict) -> list[dict]:
    return _recent_reviews(
        place,
        limit=len(place.get("reviews") or []),
    )


def _owner_name_from_business(business: dict) -> str | None:
    raw_input = business.get("raw_input") or {}
    raw_business = raw_input.get("business") or {}

    return _first_truthy(
        business.get("owner_name"),
        raw_input.get("owner_name"),
        raw_input.get("business_owner_name"),
        raw_input.get("user_name"),
        raw_business.get("owner_name"),
        raw_business.get("business_owner_name"),
    )


async def _place_for_business(business: dict) -> dict:
    place_id = business.get("place_id")
    place = await get_place_data(place_id) if place_id else None
    return place or business.get("place_payload") or {}


def _build_location(business: dict, place: dict) -> dict:
    opening_hours = place.get("opening_hours") or {}
    raw_business = (business.get("raw_input") or {}).get("business") or {}
    place_id = business.get("place_id")
    rating = _as_float(place.get("rating"))
    reviews = _as_int(place.get("user_ratings_total"))
    phone_no = _first_truthy(
        business.get("phone_no"),
        raw_business.get("phone_no"),
        place.get("formatted_phone_number"),
        place.get("international_phone_number"),
    )
    website = _first_truthy(
        business.get("website"),
        raw_business.get("website"),
        place.get("website"),
    )

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
        "phone": phone_no,
        "phone_no": phone_no,
        "website": website,
        "price_level": place.get("price_level"),
        "coordinates": _location_coordinates(place),
        "photo": _first_photo(place),
        "google_maps_url": (
            f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            if place_id
            else None
        ),
        "recent_reviews": _recent_reviews(place),
        "all_reviews": _all_reviews(place),
        "created_at": business.get("created_at"),
        "updated_at": business.get("updated_at"),
    }


def _business_key(location: dict) -> str:
    name = (location.get("business_name") or "").strip().casefold()
    category = (location.get("category") or "").strip().casefold()
    return f"{name}|{category}"


def _business_matches_name(business: dict, business_name: str) -> bool:
    return _normalize_text(business.get("business_name")) == _normalize_text(
        business_name
    )


def _review_datetime(review: dict) -> datetime | None:
    timestamp = review.get("time")
    if timestamp is None:
        return None

    try:
        return datetime.fromtimestamp(int(timestamp))
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _review_sentiment(review: dict) -> str:
    rating = _as_float(review.get("rating"))
    if rating is None:
        return "neutral"
    if rating >= 4:
        return "positive"
    if rating <= 2:
        return "negative"
    return "neutral"


def _percent(count: int, total: int) -> int:
    if not total:
        return 0
    return round((count / total) * 100)


def _sentiment_analytics(locations: list[dict]) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=30)
    recent_reviews = []

    for location in locations:
        for review in location.get("all_reviews", []):
            review_datetime = _review_datetime(review)
            if review_datetime and review_datetime >= cutoff:
                recent_reviews.append(review)

    sentiment_counter = Counter(_review_sentiment(review) for review in recent_reviews)
    total = len(recent_reviews)

    return {
        "period": "last_30_days",
        "reviews_analyzed": total,
        "avg_sentiment_analysis": {
            "positive": f"{_percent(sentiment_counter['positive'], total)}%",
            "neutral": f"{_percent(sentiment_counter['neutral'], total)}%",
            "negative": f"{_percent(sentiment_counter['negative'], total)}%",
        },
        "positive_review_percentage": _percent(
            sentiment_counter["positive"],
            total,
        ),
        "negative_review_percentage": _percent(
            sentiment_counter["negative"],
            total,
        ),
    }


async def _build_business_groups(user_id: str) -> tuple[list[dict], list[dict]]:
    user_businesses = await get_user_businesses(user_id)
    places = await asyncio.gather(
        *(_place_for_business(business) for business in user_businesses)
    )
    locations = [
        _build_location(business, place)
        for business, place in zip(user_businesses, places)
    ]

    grouped: dict[str, dict] = {}
    for business, location in zip(user_businesses, locations):
        key = _business_key(location)
        group = grouped.setdefault(
            key,
            {
                "business_id": location.get("id"),
                "context_id": location.get("context_id"),
                "business_name": location.get("business_name"),
                "category": location.get("category"),
                "owner_id": user_id,
                "owner_name": _owner_name_from_business(business),
                "created_at": location.get("created_at"),
                "updated_at": location.get("updated_at"),
                "locations": [],
                "_ratings": [],
            },
        )
        if not group.get("owner_name"):
            group["owner_name"] = _owner_name_from_business(business)
        if location.get("created_at") and (
            not group.get("created_at")
            or location["created_at"] < group["created_at"]
        ):
            group["created_at"] = location["created_at"]
        if location.get("updated_at") and (
            not group.get("updated_at")
            or location["updated_at"] > group["updated_at"]
        ):
            group["updated_at"] = location["updated_at"]
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
                "account_created": group.get("created_at"),
                "last_active": group.get("updated_at"),
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
                "phone_no": next(
                    (
                        location.get("phone_no")
                        for location in group_locations
                        if location.get("phone_no")
                    ),
                    None,
                ),
                "recent_reviews": recent_reviews,
                "locations": group_locations,
            }
        )

    return businesses, locations


async def build_business_management(user_id: str) -> dict:
    businesses, locations = await _build_business_groups(user_id)
    total_reviews = sum(location.get("reviews", 0) for location in locations)
    avg_rating = _weighted_rating(
        [(location.get("rating"), location.get("reviews", 0)) for location in locations]
    )

    return {
        "user_id": user_id,
        "total_business": len(businesses),
        "total_location": len(locations),
        "avg_rating": avg_rating,
        "total_reviews": total_reviews,
        "businesses": [
            {
                "business_name": business.get("business_name"),
                "category": business.get("category"),
                "owner_name": business.get("owner_name"),
                "phone": business.get("phone"),
                "phone_no": business.get("phone_no"),
                "website": business.get("website"),
                "location_count": business.get("location_count"),
                "reviews": business.get("reviews"),
                "ratings": business.get("rating"),
            }
            for business in businesses
        ],
    }


async def build_business_management_detail(
    *,
    user_id: str,
    business_name: str,
    overlook: str,
) -> dict:
    businesses, _ = await _build_business_groups(user_id)
    business = next(
        (
            item
            for item in businesses
            if _business_matches_name(item, business_name)
        ),
        None,
    )
    if not business:
        return {}

    normalized_overlook = _normalize_text(overlook)

    if normalized_overlook == "overview":
        return {
            "user_id": user_id,
            "business_name": business.get("business_name"),
            "overview": {
                "business_owner_name": business.get("owner_name"),
                "category": business.get("category"),
                "phone": business.get("phone"),
                "phone_no": business.get("phone_no"),
                "website": business.get("website"),
                "account_created": business.get("account_created"),
                "last_active": business.get("last_active"),
            },
        }

    if normalized_overlook in {"location", "locations", "locations/locations"}:
        return {
            "user_id": user_id,
            "business_name": business.get("business_name"),
            "locations": [
                {
                    "business_name": location.get("business_name"),
                    "address": location.get("address"),
                    "phone": location.get("phone"),
                    "phone_no": location.get("phone_no"),
                    "website": location.get("website"),
                    "reviews": location.get("reviews"),
                    "rating": location.get("rating"),
                }
                for location in business.get("locations", [])
            ],
        }

    if normalized_overlook == "analytics":
        return {
            "user_id": user_id,
            "business_name": business.get("business_name"),
            "analytics": _sentiment_analytics(business.get("locations", [])),
        }

    raise ValueError("overlook must be one of: overview, locations, analytics.")
