import json
from pathlib import Path

import requests
from app.core.config import get_settings

# Load app settings (for API keys, paths, etc.).
settings = get_settings()

# Local JSON file used as a DB-backed data source for competitors.
DATA_PATH = Path("app/db/competitor.json")

# Valid business types we treat as primary for the Google Places API call.
PRIMARY_TYPES = ["cafe", "restaurant", "bar", "bakery"]


def load_competitors_from_db() -> list[dict]:
    # Read competitors from the local JSON "DB" file if it exists.
    if not DATA_PATH.exists():
        return []

    with DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Support either a list at the root or a keyed object like {"competitors": [...]}.
    if isinstance(data, dict):
        data = data.get("competitors", [])

    # Ensure the return is always a list of competitor dicts.
    return data if isinstance(data, list) else []


def find_competitors_from_place(place_data: dict, radius: int = 1500, limit: int = 5):
    # Extract the primary place details from the Google Place Details response.
    result = place_data["result"]

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
        "key": settings.GOOGLE_PLACES_API_KEY,
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
