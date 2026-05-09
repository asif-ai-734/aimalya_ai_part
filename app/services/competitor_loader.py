import requests
from app.db.business_context_store import get_latest_business_context
from app.db.place_store import get_place_data
from app.core.config import get_settings

# Load app settings (for API keys, paths, etc.).
settings = get_settings()

# Valid business types we treat as primary for the Google Places API call.
PRIMARY_TYPES = ["cafe", "restaurant", "bar", "bakery"]


def _to_competitor_card(place: dict) -> dict:
    return {
        "place_id": place.get("place_id"),
        "name": place.get("name", "Unknown"),
        "rating": place.get("rating", 0),
        "reviews": place.get("user_ratings_total", 0),
        "price_level": place.get("price_level", 2),
    }


async def load_competitors_from_db(
    place_id: str | None = None,
    user_id: str | None = None,
) -> list[dict]:
    context = await get_latest_business_context(place_id, user_id=user_id)
    if not context:
        return []

    competitors = []
    for competitor_place_id in context.get("competitor_place_ids", []):
        place = await get_place_data(competitor_place_id)
        if place:
            competitors.append(_to_competitor_card(place))

    return competitors


def find_competitors_from_place(place_data: dict, radius: int = 1500, limit: int = 5):
    # Extract the primary place details from the Google Place Details response.
    result = place_data.get("result", place_data)

    # Pull coordinates used for the nearby search.
    lat = result["geometry"]["location"]["lat"]
    lng = result["geometry"]["location"]["lng"]
    my_place_id = result["place_id"]

    # Determine the best-matching primary business type.
    place_types = result.get("types", [])
    primary_type = next(
        (t for t in PRIMARY_TYPES if t in place_types),
        "restaurant",
    )

    # Build the Nearby Search request to Google Places.
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "type": primary_type,
        "key": settings.google_places_api_key,
    }

    # Call Google Places API and parse the JSON response.
    response = requests.get(url, params=params).json()

    # Build a normalized competitor list from the response.
    competitors = []
    for p in response.get("results", []):
        # Skip the current business if it appears in results.
        if p["place_id"] == my_place_id:
            continue

        competitors.append(
            {
                "place_id": p["place_id"],
                "name": p["name"],
                "rating": p.get("rating", 0),
                "reviews": p.get("user_ratings_total", 0),
                "price_level": p.get("price_level", 2),
            }
        )

    # Sort by rating then reviews, highest first.
    competitors.sort(key=lambda x: (x["rating"], x["reviews"]), reverse=True)

    # Return only the top N.
    return competitors[:limit]
