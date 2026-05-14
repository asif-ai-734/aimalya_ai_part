from fastapi import APIRouter, HTTPException

from app.db.business_store import get_user_businesses
from app.schemas.business_setup import (
    AddBusinessLocationRequest,
    BusinessSetupRequest,
)
from app.services.google_places_service import (
    GooglePlacesError,
    add_business_location,
    fetch_and_save_setup,
)
from app.utils.business_matching import business_matches


router = APIRouter(prefix="/businesses", tags=["Business Setup"])


@router.post("/fetch")
async def fetch_business_data(payload: BusinessSetupRequest):
    try:
        return await fetch_and_save_setup(payload)
    except GooglePlacesError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.patch("/locations")
async def add_business_location_route(payload: AddBusinessLocationRequest):
    try:
        return await add_business_location(payload)
    except GooglePlacesError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("")
async def list_businesses(user_id: str):
    businesses = await get_user_businesses(user_id)
    return {"user_id": user_id, "businesses": businesses}


@router.get("/user/{user_id}")
async def list_businesses_for_user(user_id: str):
    businesses = await get_user_businesses(user_id)
    return {"user_id": user_id, "businesses": businesses}

@router.get("/names")
async def list_business_names(user_id: str):
    businesses = await get_user_businesses(user_id)

    names = [
        business.get("business_name") or business.get("name")
        for business in businesses
        if business.get("business_name") or business.get("name")
    ]

    return {
        "user_id": user_id,
        "business_names": names
    }


@router.get("/locations")
async def get_business_locations(user_id: str, business_name: str):
    businesses = await get_user_businesses(user_id)

    matched_businesses = [
        business
        for business in businesses
        if business_matches(
            business,
            business_name=business_name,
        )
    ]

    if not matched_businesses:
        raise HTTPException(status_code=404, detail="Business not found")

    locations = []
    seen_place_ids = set()
    for business in matched_businesses:
        place_id = business.get("place_id")
        if place_id and place_id in seen_place_ids:
            continue
        if place_id:
            seen_place_ids.add(place_id)

        raw_location = (business.get("raw_input", {}) or {}).get("location") or {}
        locations.append(
            {
                "google_maps_url": raw_location.get("google_maps_url")
                or (
                    f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                    if place_id
                    else None
                ),
                "address_or_city": business.get("input_address")
                or raw_location.get("address_or_city"),
                "formatted_address": business.get("business_address"),
                "place_id": place_id,
            }
        )

    return {
        "user_id": user_id,
        "business_name": matched_businesses[0].get("business_name"),
        "locations": locations,
    }
