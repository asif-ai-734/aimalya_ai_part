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
