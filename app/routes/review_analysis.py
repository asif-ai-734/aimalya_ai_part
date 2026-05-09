# app.routes.review_analysis.py

from fastapi import APIRouter, HTTPException

from app.db.business_store import get_user_businesses

from app.services import place_loader
from app.services.review_analysis import build_reviews_analysis_page

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("/analysis")
async def reviews_analysis(
    user_id: str,
    business_name: str,
    address: str | None = None,
):
    businesses = await get_user_businesses(user_id)

    matched_business = None

    for business in businesses:
        name_matches = (
            business.get("business_name", "").strip().casefold()
            == business_name.strip().casefold()
        )

        address_matches = True

        if address:
            saved_address = (
                business.get("business_address")
                or business.get("input_address")
                or ""
            )

            address_matches = (
                address.strip().casefold()
                in saved_address.strip().casefold()
            )

        if name_matches and address_matches:
            matched_business = business
            break

    if not matched_business:
        raise HTTPException(
            status_code=404,
            detail="Business not found for this user.",
        )

    place_id = matched_business["place_id"]

    place_data = await place_loader.load_place_data(
        place_id,
        user_id=user_id,
    )

    reviews = place_data.get("reviews", [])

    return await build_reviews_analysis_page(reviews)

# #app.routes.review_analysis.py
# from fastapi import APIRouter
# from app.services import place_loader
# from app.services.review_analysis import build_reviews_analysis_page

# router = APIRouter(prefix="/reviews", tags=["Reviews"])


# @router.get("/analysis")
# async def reviews_analysis(
#     place_id: str | None = None,
#     user_id: str | None = None,
# ):
#     place_data = await place_loader.load_place_data(place_id, user_id=user_id)
#     reviews = place_data.get("reviews", [])
#     return await build_reviews_analysis_page(reviews)
