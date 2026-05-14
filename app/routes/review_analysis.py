# app.routes.review_analysis.py

from fastapi import APIRouter, HTTPException

from app.services import place_loader
from app.services.business_lookup import find_user_business
from app.services.review_analysis import build_reviews_analysis_page
from app.utils.counting_route import CountingRoute

router = APIRouter(prefix="/reviews", tags=["Reviews"], route_class=CountingRoute)


@router.get("/analysis")
async def reviews_analysis(
    user_id: str,
    business_name: str,
    address: str | None = None,
):
    matched_business = await find_user_business(
        user_id=user_id,
        business_name=business_name,
        address=address,
    )

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

