import asyncio

from fastapi import APIRouter, HTTPException

from app.db.business_store import (
    get_business_profile,
    update_business_profile,
)
from app.services.google_places_service import _expand_and_extract_place_id

router = APIRouter(prefix="/business-profile", tags=["Business Profile"])


@router.get("")
async def get_business_profile_route(
    user_id: str,
    business_name: str,
    location: str,
):
    result = await get_business_profile(
        user_id=user_id,
        business_name=business_name,
        location=location,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Business not found.",
        )

    return result


@router.patch("")
async def update_business_profile_route(
    user_id: str,
    existing_business_name: str,
    existing_location: str,
    new_business_name: str | None = None,
    category: str | None = None,
    new_location: str | None = None,
    map_url: str | None = None,
    phone_no: str | None = None,
    website: str | None = None,
):
    place_id = None
    if map_url:
        place_id = await asyncio.to_thread(
            _expand_and_extract_place_id,
            map_url,
        )

    result = await update_business_profile(
        user_id=user_id,
        existing_business_name=existing_business_name,
        existing_location=existing_location,
        new_business_name=new_business_name,
        category=category,
        new_location=new_location,
        place_id=place_id,
        phone_no=phone_no,
        website=website,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Business not found.",
        )

    return result
