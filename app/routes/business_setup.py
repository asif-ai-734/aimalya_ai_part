from fastapi import APIRouter, HTTPException

from app.db.business_store import get_user_businesses
from app.schemas.business_setup import BusinessSetupRequest
from app.services.google_places_service import (
    GooglePlacesError,
    fetch_and_save_setup,
)


router = APIRouter(prefix="/businesses", tags=["Business Setup"])


@router.post("/fetch")
async def fetch_business_data(payload: BusinessSetupRequest):
    try:
        return await fetch_and_save_setup(payload)
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

    matched_business = next(
        (
            business for business in businesses
            if business.get("business_name") == business_name
        ),
        None,
    )

    if not matched_business:
        raise HTTPException(status_code=404, detail="Business not found")

    locations = (
        matched_business
        .get("raw_input", {})
        .get("business", {})
        .get("locations", [])
    )

    return {
        "user_id": user_id,
        "business_name": matched_business.get("business_name"),
        "locations": locations,
    }