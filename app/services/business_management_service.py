import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.db.business_store import (
    get_all_user_businesses,
    update_business_account_status,
)
from app.db.place_store import get_place_data
from app.db.route_hit_store import get_recent_route_events


PhotoUrlBuilder = Callable[[str | None], str | None]


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


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def _time_ago(value: datetime) -> str:
    seconds = max(int((datetime.utcnow() - value).total_seconds()), 0)
    if seconds < 60:
        return "just now"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = hours // 24
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"

    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"

    years = months // 12
    return f"{years} year{'s' if years != 1 else ''} ago"


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _average_rating(ratings: list[float | None]) -> float:
    valid = [rating for rating in ratings if rating is not None]
    if not valid:
        return 0.0

    return round(sum(valid) / len(valid), 1)


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


def _first_photo(
    place: dict,
    photo_url_builder: PhotoUrlBuilder | None = None,
) -> dict | None:
    photos = place.get("photos") or []
    if not photos:
        return None

    photo = photos[0]
    photo_reference = photo.get("photo_reference")
    return {
        "photo_reference": photo_reference,
        "photo_url": photo_url_builder(photo_reference) if photo_url_builder else None,
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


def _build_location(
    business: dict,
    place: dict,
    photo_url_builder: PhotoUrlBuilder | None = None,
) -> dict:
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
        "owner_id": business.get("user_id"),
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
        "account_status": business.get("account_status") or "active",
        "is_suspended": bool(business.get("is_suspended")),
        "open_now": opening_hours.get("open_now"),
        "rating": rating,
        "rating_stars": _rating_stars(rating),
        "reviews": reviews,
        "phone": phone_no,
        "phone_no": phone_no,
        "website": website,
        "price_level": place.get("price_level"),
        "coordinates": _location_coordinates(place),
        "photo": _first_photo(place, photo_url_builder),
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
    owner_id = (location.get("owner_id") or "").strip().casefold()
    name = (location.get("business_name") or "").strip().casefold()
    category = (location.get("category") or "").strip().casefold()
    return f"{owner_id}|{name}|{category}"


def _business_matches_name(business: dict, business_name: str) -> bool:
    return _normalize_text(business.get("business_name")) == _normalize_text(
        business_name
    )


def _activity_item(
    *,
    activity_type: str,
    title: str,
    subtitle: str,
    timestamp: datetime,
    metadata: dict | None = None,
) -> dict:
    return {
        "type": activity_type,
        "title": title,
        "subtitle": subtitle,
        "time_ago": _time_ago(timestamp),
        "created_at": timestamp.isoformat(),
        "metadata": metadata or {},
    }


async def _recent_activity(
    business: dict,
    *,
    user_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    activities = []

    for location in business.get("locations", []):
        created_at = _parse_datetime(location.get("created_at"))
        if created_at:
            activities.append(
                _activity_item(
                    activity_type="new_location_added",
                    title="New location added",
                    subtitle="All locations",
                    timestamp=created_at,
                    metadata={
                        "business_name": location.get("business_name"),
                        "address": location.get("address"),
                        "place_id": location.get("place_id"),
                    },
                )
            )

    activity_user_id = user_id or business.get("owner_id")
    if activity_user_id:
        report_events = await get_recent_route_events(
            activity_user_id,
            ["/reports/monthly"],
            limit=limit,
        )
        for event in report_events:
            created_at = _parse_datetime(event.get("created_at"))
            if not created_at:
                continue
            activities.append(
                _activity_item(
                    activity_type="monthly_report_generated",
                    title="Monthly report generated",
                    subtitle="All locations",
                    timestamp=created_at,
                    metadata={"route_path": event.get("route_path")},
                )
            )

    activities.sort(key=lambda item: item["created_at"], reverse=True)
    return activities[:limit]


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


async def _build_business_groups(
    user_id: str | None = None,
    photo_url_builder: PhotoUrlBuilder | None = None,
) -> tuple[list[dict], list[dict]]:
    user_businesses = await get_all_user_businesses()
    if user_id:
        user_businesses = [
            business
            for business in user_businesses
            if business.get("user_id") == user_id
        ]
    places = await asyncio.gather(
        *(_place_for_business(business) for business in user_businesses)
    )
    locations = [
        _build_location(business, place, photo_url_builder)
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
                "owner_id": business.get("user_id"),
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
        group["_ratings"].append(location.get("rating"))

    businesses = []
    for group in grouped.values():
        group_locations = group["locations"]
        reviews = sum(location.get("reviews", 0) for location in group_locations)
        rating = _average_rating(group["_ratings"])
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
                "account_status": (
                    "suspended"
                    if any(
                        location.get("account_status") == "suspended"
                        for location in group_locations
                    )
                    else "active"
                ),
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


async def build_business_management(
    user_id: str | None = None,
    photo_url_builder: PhotoUrlBuilder | None = None,
) -> dict:
    businesses, locations = await _build_business_groups(
        user_id=user_id,
        photo_url_builder=photo_url_builder,
    )
    total_reviews = sum(location.get("reviews", 0) for location in locations)
    avg_rating = _average_rating([location.get("rating") for location in locations])

    return {
        "total_business": len(businesses),
        "total_location": len(locations),
        "avg_rating": avg_rating,
        "total_reviews": total_reviews,
        "businesses": [
            {
                "business_name": business.get("business_name"),
                "category": business.get("category"),
                "owner_id": business.get("owner_id"),
                "owner_name": business.get("owner_name"),
                "phone": business.get("phone"),
                "phone_no": business.get("phone_no"),
                "website": business.get("website"),
                "photo": business.get("primary_photo"),
                "primary_photo": business.get("primary_photo"),
                "location_count": business.get("location_count"),
                "reviews": business.get("reviews"),
                "average_rating": business.get("rating"),
                "ratings": business.get("rating"),
                "account_status": business.get("account_status"),
                "is_suspended": business.get("account_status") == "suspended",
            }
            for business in businesses
        ],
    }

async def build_business_categories() -> dict:
    businesses, _ = await _build_business_groups()

    category_counter = Counter()

    for business in businesses:
        category = (
            business.get("category")
            or "unknown"
        ).strip().lower()

        category_counter[category] += 1

    categories = [
        {
            "category": category,
            "business_count": count,
        }
        for category, count in sorted(
            category_counter.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    return {
        "total_categories": len(categories),
        "categories": categories,
    }

async def build_business_management_detail(
    *,
    business_name: str | None = None,
    user_id: str | None = None,
    overlook: str,
    photo_url_builder: PhotoUrlBuilder | None = None,
) -> dict:
    businesses, _ = await _build_business_groups(
        user_id=user_id,
        photo_url_builder=photo_url_builder,
    )
    if business_name:
        business = next(
            (
                item
                for item in businesses
                if _business_matches_name(item, business_name)
            ),
            None,
        )
    else:
        business = businesses[0] if businesses else None

    if not business:
        return {}

    normalized_overlook = _normalize_text(overlook)

    if normalized_overlook == "overview":
        recent_activity = await _recent_activity(
            business,
            user_id=user_id,
        )
        return {
            "business_name": business.get("business_name"),
            "owner_id": business.get("owner_id"),
            "average_rating": business.get("rating"),
            "rating_stars": business.get("rating_stars"),
            "recent_activity": recent_activity,
            "overview": {
                "business_owner_name": business.get("owner_name"),
                "category": business.get("category"),
                "average_rating": business.get("rating"),
                "rating_stars": business.get("rating_stars"),
                "phone": business.get("phone"),
                "phone_no": business.get("phone_no"),
                "website": business.get("website"),
                "photo": business.get("primary_photo"),
                "primary_photo": business.get("primary_photo"),
                "account_created": business.get("account_created"),
                "last_active": business.get("last_active"),
                "account_status": business.get("account_status"),
                "is_suspended": business.get("account_status") == "suspended",
            },
        }

    if normalized_overlook in {"location", "locations", "locations/locations"}:
        return {
            "business_name": business.get("business_name"),
            "owner_id": business.get("owner_id"),
            "average_rating": business.get("rating"),
            "rating_stars": business.get("rating_stars"),
            "locations": [
                {
                    "business_name": location.get("business_name"),
                    "address": location.get("address"),
                    "phone": location.get("phone"),
                    "phone_no": location.get("phone_no"),
                    "website": location.get("website"),
                    "photo": location.get("photo"),
                    "reviews": location.get("reviews"),
                    "rating": location.get("rating"),
                    "account_status": location.get("account_status"),
                    "is_suspended": location.get("is_suspended"),
                }
                for location in business.get("locations", [])
            ],
        }

    if normalized_overlook == "analytics":
        return {
            "business_name": business.get("business_name"),
            "owner_id": business.get("owner_id"),
            "average_rating": business.get("rating"),
            "rating_stars": business.get("rating_stars"),
            "analytics": _sentiment_analytics(business.get("locations", [])),
        }

    raise ValueError("overlook must be one of: overview, locations, analytics.")


async def update_business_management_account_status(
    *,
    user_id: str,
    business_name: str,
    action: str,
) -> dict | None:
    normalized_action = _normalize_text(action)
    if normalized_action == "suspend":
        account_status = "suspended"
    elif normalized_action == "unsuspend":
        account_status = "active"
    else:
        raise ValueError("action must be one of: suspend, unsuspend.")

    result = await update_business_account_status(
        user_id=user_id,
        business_name=business_name,
        account_status=account_status,
    )
    if not result:
        return None

    return {
        "user_id": result.get("user_id"),
        "business_name": result.get("business_name"),
        "action": normalized_action,
        "account_status": result.get("account_status"),
        "is_suspended": result.get("is_suspended"),
        "updated_count": result.get("updated_count"),
    }
