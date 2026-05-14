import asyncio
from datetime import datetime
import html
import re
from urllib.parse import parse_qs, unquote, urlparse

import requests

from app.core.config import get_settings
from app.db.business_context_store import (
    get_latest_business_context,
    save_business_context,
)
from app.db.business_store import get_user_businesses, save_user_businesses
from app.db.place_store import upsert_place_data
from app.schemas.business_setup import (
    AddBusinessLocationRequest,
    BusinessInput,
    BusinessLocationInput,
    BusinessSetupRequest,
)
from app.utils.business_matching import business_matches


settings = get_settings()

TEXT_SEARCH_NEW_URL = "https://places.googleapis.com/v1/places:searchText"
NEARBY_SEARCH_NEW_URL = "https://places.googleapis.com/v1/places:searchNearby"
DETAILS_NEW_URL = "https://places.googleapis.com/v1/places/{place_id}"

PLACE_DETAILS_FIELD_MASK = ",".join(
    [
        "id",
        "name",
        "displayName",
        "businessStatus",
        "types",
        "formattedAddress",
        "rating",
        "userRatingCount",
        "priceLevel",
        "regularOpeningHours",
        "nationalPhoneNumber",
        "internationalPhoneNumber",
        "websiteUri",
        "location",
        "viewport",
        "accessibilityOptions",
        "servesVegetarianFood",
        "takeout",
        "dineIn",
        "delivery",
        "photos",
        "reviews",
    ]
)
TEXT_SEARCH_FIELD_MASK = "places.id"
NEARBY_SEARCH_FIELD_MASK = "places.id,places.rating,places.userRatingCount"
MAPS_EXPAND_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

PRIMARY_TYPES = {
    "bakery": "bakery",
    "bar": "bar",
    "cafe": "cafe",
    "coffee": "cafe",
    "coffee house": "cafe",
    "restaurant": "restaurant",
}


class GooglePlacesError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _request_json(
    method: str,
    url: str,
    *,
    field_mask: str,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    headers = {
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": field_mask,
    }
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    try:
        response = requests.request(
            method,
            url,
            params=params,
            json=json_body,
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise GooglePlacesError(f"Google Places request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError:
        data = {}

    if not response.ok:
        error = data.get("error", {})
        message = error.get("message") or response.text or "Google Places error."
        status_code = response.status_code if response.status_code < 500 else 502
        raise GooglePlacesError(message, status_code=status_code)

    return data


def _google_status_error(data: dict, fallback: str) -> GooglePlacesError:
    error = data.get("error", {})
    status = error.get("status") or data.get("status", "UNKNOWN")
    message = error.get("message") or data.get("error_message") or fallback
    status_code = 404 if status in {"NOT_FOUND", "ZERO_RESULTS"} else 502
    return GooglePlacesError(f"{message} Google status: {status}", status_code)


def _clean_review_text(text: str | None) -> str:
    text = html.unescape(text or "")
    return re.sub(r"<[^>]+>", "", text).strip()


def _normalize_reviews(place: dict) -> dict:
    for review in place.get("reviews", []):
        review["text"] = _clean_review_text(review.get("text"))
    return place


def _localized_text(value: dict | str | None) -> str | None:
    if isinstance(value, dict):
        return value.get("text")
    return value


def _place_id_from_resource(value: str | None) -> str | None:
    if not value:
        return None
    return value.rsplit("/", 1)[-1]


def _price_level_to_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return PRICE_LEVELS.get(value)


def _lat_lng(value: dict | None) -> dict:
    value = value or {}
    return {
        "lat": value.get("lat", value.get("latitude")),
        "lng": value.get("lng", value.get("longitude")),
    }


def _viewport(value: dict | None) -> dict:
    value = value or {}
    if "northeast" in value or "southwest" in value:
        return value
    return {
        "northeast": _lat_lng(value.get("high")),
        "southwest": _lat_lng(value.get("low")),
    }


def _unix_time(value: str | int | None) -> int | None:
    if value is None or isinstance(value, int):
        return value
    try:
        timestamp = value.replace("Z", "+00:00")
        timestamp = re.sub(
            r"(\.\d{6})\d+([+-]\d\d:\d\d)$",
            r"\1\2",
            timestamp,
        )
        return int(datetime.fromisoformat(timestamp).timestamp())
    except ValueError:
        return None


def _author_names(attributions: list[dict] | None) -> list[str]:
    return [
        item.get("uri") or item.get("displayName")
        for item in attributions or []
        if item.get("uri") or item.get("displayName")
    ]


def _normalize_new_place(place: dict) -> dict:
    if "place_id" in place:
        return _normalize_reviews(place)

    opening_hours = place.get("regularOpeningHours", {})
    accessibility = place.get("accessibilityOptions", {})

    normalized = {
        "place_id": place.get("id") or _place_id_from_resource(place.get("name")),
        "name": _localized_text(place.get("displayName")),
        "business_status": place.get("businessStatus"),
        "types": place.get("types", []),
        "formatted_address": place.get("formattedAddress"),
        "rating": place.get("rating"),
        "user_ratings_total": place.get("userRatingCount"),
        "price_level": _price_level_to_int(place.get("priceLevel")),
        "opening_hours": {
            "open_now": opening_hours.get("openNow"),
            "weekday_text": opening_hours.get("weekdayDescriptions", []),
        },
        "formatted_phone_number": place.get("nationalPhoneNumber"),
        "international_phone_number": place.get("internationalPhoneNumber"),
        "website": place.get("websiteUri"),
        "geometry": {
            "location": _lat_lng(place.get("location")),
            "viewport": _viewport(place.get("viewport")),
        },
        "wheelchair_accessible_entrance": accessibility.get(
            "wheelchairAccessibleEntrance"
        ),
        "serves_vegetarian_food": place.get("servesVegetarianFood"),
        "takeout": place.get("takeout"),
        "dine_in": place.get("dineIn"),
        "delivery": place.get("delivery"),
        "photos": [
            {
                "height": photo.get("heightPx"),
                "width": photo.get("widthPx"),
                "photo_reference": photo.get("name"),
                "html_attributions": _author_names(
                    photo.get("authorAttributions")
                ),
            }
            for photo in place.get("photos", [])
        ],
        "reviews": [
            {
                "author_name": review.get("authorAttribution", {}).get(
                    "displayName"
                ),
                "rating": review.get("rating"),
                "text": _localized_text(
                    review.get("text") or review.get("originalText")
                ),
                "time": _unix_time(review.get("publishTime")),
                "relative_time_description": review.get(
                    "relativePublishTimeDescription"
                ),
                "language": (
                    review.get("text", {}).get("languageCode")
                    if isinstance(review.get("text"), dict)
                    else None
                ),
            }
            for review in place.get("reviews", [])
        ],
    }
    return _normalize_reviews(normalized)


def _extract_place_id_from_url(value: str | None) -> str | None:
    if not value:
        return None

    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    for key in ("place_id", "query_place_id"):
        if query.get(key):
            return query[key][0]

    match = re.search(r"(?:place_id:|placeid=)([^!&?/]+)", value)
    if match:
        return match.group(1)

    common_match = re.search(r"(ChI[A-Za-z0-9_-]+)", value)
    if common_match:
        return common_match.group(1)

    resource_match = re.search(r"places/([^!&?/]+)", value)
    if resource_match:
        return resource_match.group(1)

    return None


def _decode_url_candidate(value: str | None) -> str | None:
    if not value:
        return None

    decoded = html.unescape(value).strip()
    for _ in range(2):
        decoded = decoded.replace("\\u0026", "&")
        decoded = decoded.replace("\\u003d", "=")
        decoded = decoded.replace("\\/", "/")
        decoded = unquote(decoded)

    return decoded.strip()


def _is_google_maps_url(value: str | None) -> bool:
    if not value:
        return False

    parsed = urlparse(value)
    host = parsed.netloc.casefold()
    path = parsed.path.casefold()

    return (
        host == "maps.app.goo.gl"
        or host.endswith(".goo.gl")
        or host.startswith("maps.google.")
        or ("google." in host and path.startswith("/maps"))
    )


def _is_short_maps_url(value: str | None) -> bool:
    if not value:
        return False

    host = urlparse(value).netloc.casefold()
    return host == "maps.app.goo.gl" or host.endswith(".goo.gl")


def _add_url_candidate(candidates: list[str], value: str | None) -> None:
    decoded = _decode_url_candidate(value)
    if not decoded:
        return

    nested_values = []
    parsed = urlparse(decoded)
    query = parse_qs(parsed.query)
    for key in ("q", "url", "u", "continue"):
        nested_values.extend(query.get(key, []))

    values = [decoded]
    values.extend(_decode_url_candidate(item) for item in nested_values)

    for item in values:
        if item and item not in candidates:
            candidates.append(item)


def _urls_from_response_text(text: str | None) -> list[str]:
    decoded = _decode_url_candidate(text)
    if not decoded:
        return []

    return re.findall(r"https?://[^\s\"'<>]+", decoded)


def _expanded_url_candidates(value: str | None) -> list[str]:
    if not value:
        return []

    candidates: list[str] = []
    _add_url_candidate(candidates, _normalize_url_candidate(value))

    try:
        response = requests.get(
            candidates[0],
            allow_redirects=True,
            headers=MAPS_EXPAND_HEADERS,
            timeout=15,
        )
    except requests.RequestException:
        return candidates

    for item in [*response.history, response]:
        _add_url_candidate(candidates, item.url)
        _add_url_candidate(candidates, item.headers.get("Location"))

    content_type = response.headers.get("Content-Type", "")
    if "text" in content_type or "html" in content_type:
        for url in _urls_from_response_text(response.text):
            _add_url_candidate(candidates, url)

    return candidates


def _best_expanded_maps_url(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if _is_google_maps_url(candidate) and not _is_short_maps_url(candidate):
            return candidate

    for candidate in candidates:
        if _is_google_maps_url(candidate):
            return candidate

    return candidates[0] if candidates else None


def _coordinates_from_maps_path(path_parts: list[str]) -> tuple[float, float] | None:
    for part in path_parts:
        match = re.match(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", part)
        if match:
            return float(match.group(1)), float(match.group(2))
    return None


def _expand_and_extract_place_id(value: str | None) -> str | None:
    place_id = _extract_place_id_from_url(value)
    if place_id or not value:
        return place_id

    for candidate in _expanded_url_candidates(value):
        place_id = _extract_place_id_from_url(candidate)
        if place_id:
            return place_id

    return None


def _summary(place: dict) -> dict:
    return {
        "place_id": place.get("place_id"),
        "name": place.get("name"),
        "formatted_address": place.get("formatted_address"),
        "rating": place.get("rating"),
        "user_ratings_total": place.get("user_ratings_total"),
        "reviews_saved": len(place.get("reviews", [])),
    }


def summarize_place(place: dict) -> dict:
    return _summary(place)


def _map_url(place_id: str | None) -> str | None:
    if not place_id:
        return None

    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _existing_business_category(business: dict) -> str:
    place_payload = business.get("place_payload") or {}
    place_types = place_payload.get("types") or []
    return (
        business.get("business_category")
        or (place_types[0] if place_types else None)
        or "business"
    )


def _business_location_response(record: dict, place: dict) -> dict:
    place_id = record.get("place_id") or place.get("place_id")
    return {
        "business_name": record.get("business_name"),
        "category": record.get("business_category"),
        "location": record.get("business_address") or record.get("input_address"),
        "input_location": record.get("input_address"),
        "place_id": place_id,
        "map_url": _map_url(place_id),
        "phone_no": record.get("phone_no"),
        "website": record.get("website"),
    }


async def _find_existing_businesses(
    *,
    user_id: str,
    business_name: str,
) -> list[dict]:
    businesses = await get_user_businesses(user_id)
    return [
        business
        for business in businesses
        if business_matches(
            business,
            business_name=business_name,
        )
    ]


def _query_from_location(
    business: BusinessInput,
    location: BusinessLocationInput | None,
) -> str:
    parts = []
    if location:
        parts.append(location.address_or_city)
    parts.extend([business.name, business.category])
    return " ".join(str(part).strip() for part in parts if part).strip()


def _category_to_place_type(category: str | None, place: dict | None = None) -> str:
    category_key = (category or "").strip().lower()
    for keyword, place_type in PRIMARY_TYPES.items():
        if keyword in category_key:
            return place_type

    for place_type in (place.get("types", []) if place else []):
        if place_type in PRIMARY_TYPES.values():
            return place_type

    return "restaurant"


def _fetch_place_details_sync(place_id: str) -> dict:
    place_id = _place_id_from_resource(place_id)
    data = _request_json(
        "GET",
        DETAILS_NEW_URL.format(place_id=place_id),
        field_mask=PLACE_DETAILS_FIELD_MASK,
    )

    if not data.get("id"):
        raise _google_status_error(data, "Could not fetch place details.")

    return _normalize_new_place(data)


async def fetch_place_details(place_id: str) -> dict:
    return await asyncio.to_thread(_fetch_place_details_sync, place_id)


def _find_place_id_from_text_sync(
    query: str,
    location_bias: dict | None = None,
) -> str:
    body = {
        "textQuery": query,
        "pageSize": 1,
    }
    if location_bias:
        body["locationBias"] = location_bias

    data = _request_json(
        "POST",
        TEXT_SEARCH_NEW_URL,
        field_mask=TEXT_SEARCH_FIELD_MASK,
        json_body=body,
    )

    places = data.get("places", [])
    if not places:
        raise GooglePlacesError(f"No Google Place found for: {query}", 404)

    place = places[0]
    place_id = place.get("id") or _place_id_from_resource(place.get("name"))
    if not place_id:
        raise GooglePlacesError(f"No Google Place found for: {query}", 404)

    return place_id


async def find_place_id_from_text(
    query: str,
    location_bias: dict | None = None,
) -> str:
    return await asyncio.to_thread(
        _find_place_id_from_text_sync,
        query,
        location_bias,
    )


async def resolve_place(
    business: BusinessInput,
    location: BusinessLocationInput | None = None,
) -> dict:
    maps_url = None
    place_id = None
    if location:
        maps_url = location.google_maps_url
        place_id = await asyncio.to_thread(
            _expand_and_extract_place_id,
            maps_url,
        )

    if not place_id:
        query = _query_from_location(business, location)
        if not query and maps_url:
            query = maps_url
        if not query:
            raise GooglePlacesError(
                "Provide a Google Maps URL, business name, or address_or_city.",
                status_code=400,
            )
        location_bias = _location_bias_from_url(maps_url) if maps_url else None
        place_id = await find_place_id_from_text(query, location_bias)

    return await fetch_place_details(place_id)


def _normalize_url_candidate(value: str) -> str:
    cleaned = value.strip()
    if re.match(r"^[a-z][a-z0-9+.-]*://", cleaned, re.IGNORECASE):
        return cleaned
    if "google." in cleaned or "goo.gl" in cleaned:
        return f"https://{cleaned}"
    return cleaned


def _maps_path_parts(value: str) -> list[str]:
    parsed = urlparse(value)
    return [
        unquote(part).replace("+", " ").strip()
        for part in parsed.path.split("/")
        if part.strip()
    ]


def _query_from_url_or_text(value: str) -> str:
    normalized = _normalize_url_candidate(value)
    parsed = urlparse(normalized)
    query = parse_qs(parsed.query)
    for key in ("q", "query", "destination", "daddr"):
        if query.get(key):
            return unquote(query[key][0]).replace("+", " ").strip()

    path_parts = _maps_path_parts(normalized)
    if "place" in path_parts:
        place_index = path_parts.index("place")
        if len(path_parts) > place_index + 1:
            return path_parts[place_index + 1]

    for part in path_parts:
        if part and not part.startswith("@") and not part.startswith("data="):
            if part not in {"maps", "place", "dir", "search"}:
                return part

    if path_parts:
        return path_parts[-1]

    return value.strip()


def _location_bias_from_url(value: str) -> dict | None:
    normalized = _normalize_url_candidate(value)
    coordinates = _coordinates_from_maps_path(_maps_path_parts(normalized))
    if not coordinates:
        return None

    lat, lng = coordinates
    return {
        "circle": {
            "center": {
                "latitude": lat,
                "longitude": lng,
            },
            "radius": 5000.0,
        }
    }


async def resolve_place_from_url_or_text(value: str) -> dict:
    normalized = _normalize_url_candidate(value)
    place_id = _extract_place_id_from_url(normalized)
    if place_id:
        return await fetch_place_details(place_id)

    expanded_candidates = await asyncio.to_thread(
        _expanded_url_candidates,
        normalized,
    )
    expanded_url = _best_expanded_maps_url(expanded_candidates) or normalized
    place_id = next(
        (
            candidate_place_id
            for candidate in expanded_candidates
            for candidate_place_id in [_extract_place_id_from_url(candidate)]
            if candidate_place_id
        ),
        None,
    )

    if not place_id:
        query = _query_from_url_or_text(expanded_url)
        if not query:
            raise GooglePlacesError(
                "Provide a valid Google Maps URL or competitor name.",
                status_code=400,
            )
        place_id = await find_place_id_from_text(
            query,
            _location_bias_from_url(expanded_url),
        )

    return await fetch_place_details(place_id)


def _nearby_competitor_candidates_sync(
    place: dict,
    category: str | None,
    *,
    radius: int,
    limit: int,
) -> list[str]:
    location = place.get("geometry", {}).get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    if lat is None or lng is None:
        return []

    data = _request_json(
        "POST",
        NEARBY_SEARCH_NEW_URL,
        field_mask=NEARBY_SEARCH_FIELD_MASK,
        json_body={
            "includedTypes": [_category_to_place_type(category, place)],
            "maxResultCount": limit,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": lat,
                        "longitude": lng,
                    },
                    "radius": float(radius),
                }
            },
        },
    )

    candidates = [
        result
        for result in data.get("places", [])
        if (
            (result.get("id") or _place_id_from_resource(result.get("name")))
            and (
                result.get("id") or _place_id_from_resource(result.get("name"))
            )
            != place.get("place_id")
        )
    ]
    candidates.sort(
        key=lambda item: (
            item.get("rating") or 0,
            item.get("userRatingCount") or 0,
        ),
        reverse=True,
    )
    return [
        item.get("id") or _place_id_from_resource(item.get("name"))
        for item in candidates[:limit]
    ]


async def find_nearby_competitors(
    place: dict,
    category: str | None,
    *,
    radius: int = 1500,
    limit: int = 5,
) -> list[dict]:
    place_ids = await asyncio.to_thread(
        _nearby_competitor_candidates_sync,
        place,
        category,
        radius=radius,
        limit=limit,
    )

    return list(
        await asyncio.gather(
            *(fetch_place_details(place_id) for place_id in place_ids)
        )
    )


async def _resolve_business_location(
    business: BusinessInput,
    location: BusinessLocationInput | None,
) -> tuple[dict, dict]:
    place = await resolve_place(business, location)
    return place, {
        "business_name": business.name,
        "business_category": business.category,
        "phone_no": business.phone_no,
        "website": business.website,
        "business_address": place.get("formatted_address")
        or (location.address_or_city if location else None),
        "input_address": location.address_or_city if location else None,
        "place_id": place["place_id"],
        "place_payload": place,
        "raw_input": {
            "business": business.model_dump(),
            "location": location.model_dump() if location else None,
        },
    }


async def fetch_and_save_setup(payload: BusinessSetupRequest) -> dict:
    businesses = payload.businesses
    tasks = [
        _resolve_business_location(business, location)
        for business in businesses
        for location in (business.locations or [None])
    ]
    resolved = await asyncio.gather(*tasks)
    places = [place for place, _ in resolved]
    business_records = [record for _, record in resolved]

    for place in places:
        await upsert_place_data(place)

    if not places:
        raise GooglePlacesError(
            "No business locations were provided.",
            status_code=400,
        )

    primary_place = places[0]
    primary_place_id = primary_place["place_id"]
    primary_business = businesses[0]
    primary_locations = primary_business.locations or [None]
    primary_location = primary_locations[0]
    primary_business_name = primary_business.name
    primary_business_address = (
        primary_place.get("formatted_address")
        or (primary_location.address_or_city if primary_location else None)
    )
    primary_business_category = primary_business.category

    place_ids = []
    for place in places:
        if place.get("place_id") and place["place_id"] not in place_ids:
            place_ids.append(place["place_id"])

    raw_input = payload.model_dump()
    context_id = await save_business_context(
        user_id=payload.user_id,
        primary_place_id=primary_place_id,
        place_ids=place_ids,
        competitor_place_ids=[],
        business_name=primary_business_name,
        business_address=primary_business_address,
        business_category=primary_business_category,
        report_frequency=None,
        goals=[],
        raw_input=raw_input,
    )
    await save_user_businesses(
        context_id=context_id,
        user_id=payload.user_id,
        businesses=business_records,
    )

    return {
        "status": "saved",
        "user_id": payload.user_id,
        "context_id": context_id,
        "default_place_id": primary_place_id,
        "places": [_summary(place) for place in places],
        "competitors": [],
        "competitor_errors": [],
        "reviews_note": "Google Place Details returns up to five reviews per place.",
    }


async def add_business_location(payload: AddBusinessLocationRequest) -> dict:
    existing_businesses = await _find_existing_businesses(
        user_id=payload.user_id,
        business_name=payload.business_name,
    )

    if not existing_businesses:
        raise GooglePlacesError(
            "Business not found for this user.",
            status_code=404,
        )

    existing_business = existing_businesses[0]
    business = BusinessInput(
        name=existing_business.get("business_name") or payload.business_name,
        category=_existing_business_category(existing_business),
        phone_no=_first_present(payload.phone_no, existing_business.get("phone_no")),
        website=_first_present(payload.website, existing_business.get("website")),
        locations=[
            BusinessLocationInput(
                google_maps_url=payload.maps_url,
                address_or_city=payload.location,
            )
        ],
    )
    location = business.locations[0]
    place, business_record = await _resolve_business_location(
        business,
        location,
    )

    await upsert_place_data(place)

    source_context = await get_latest_business_context(
        existing_business.get("place_id"),
        user_id=payload.user_id,
    )
    context_id = await save_business_context(
        user_id=payload.user_id,
        primary_place_id=place["place_id"],
        place_ids=[place["place_id"]],
        competitor_place_ids=[],
        business_name=business.name,
        business_address=business_record.get("business_address"),
        business_category=business.category,
        report_frequency=source_context.get("report_frequency")
        if source_context
        else None,
        goals=[],
        raw_input={
            "add_location": payload.model_dump(),
            "source_context_id": source_context.get("id")
            if source_context
            else None,
        },
    )

    await save_user_businesses(
        context_id=context_id,
        user_id=payload.user_id,
        businesses=[business_record],
    )

    return {
        "status": "saved",
        "user_id": payload.user_id,
        "context_id": context_id,
        "business_name": business.name,
        "location": _business_location_response(business_record, place),
        "place": _summary(place),
        "reviews_note": "Google Place Details returns up to five reviews per place.",
    }
