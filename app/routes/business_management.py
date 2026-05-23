from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request

from app.services.business_management_service import (
    build_business_management,
    build_business_management_detail,
    build_business_categories,
    update_business_management_account_status,
)
from app.db.place_store import (
    get_place_rating_snapshot_at_or_before,
    upsert_place_data,
)
from app.services.business_lookup import find_user_business
from app.services.google_places_service import GooglePlacesError, fetch_place_details
from app.services.rating_drop_service import (
    build_rating_drop_report,
    rating_snapshot_cutoff,
)
from app.schemas.business_management import BusinessAccountStatusRequest
from app.utils.counting_route import CountingRoute

router = APIRouter(prefix="/businesses", tags=["Business Management"], route_class=CountingRoute)


def _photo_proxy_url(
    request: Request,
    photo_reference: str | None,
    *,
    maxwidth: int = 800,
) -> str | None:
    if not photo_reference:
        return None

    query = urlencode(
        {
            "photo_reference": photo_reference,
            "maxwidth": maxwidth,
        }
    )
    return f"{request.url_for('ai_insights_place_photo')}?{query}"


@router.get("/management")
async def business_management(
    request: Request,
    user_id: str | None = None,
):
    return await build_business_management(
        user_id=user_id,
        photo_url_builder=lambda reference: _photo_proxy_url(request, reference)
    )


@router.patch("/management")
async def update_business_account_status(payload: BusinessAccountStatusRequest):
    try:
        result = await update_business_management_account_status(
            user_id=payload.user_id,
            business_name=payload.business_name,
            action=payload.action,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Business not found for this user.",
        )

    return result


@router.get("/management/rating-drop")
async def business_rating_drop(
    user_id: str,
    business_name: str,
    location: str,
    report_frequency: str,
):
    matched_business = await find_user_business(
        user_id=user_id,
        business_name=business_name,
        address=location,
    )

    if not matched_business:
        raise HTTPException(
            status_code=404,
            detail="Business not found for this user and location.",
        )

    try:
        previous_cutoff = rating_snapshot_cutoff(report_frequency)
        current_place = await fetch_place_details(matched_business["place_id"])
        await upsert_place_data(current_place)
        current_snapshot = {
            "rating": current_place.get("rating"),
            "user_ratings_total": current_place.get("user_ratings_total"),
            "recorded_at": datetime.utcnow().isoformat(),
        }
        previous_snapshot = await get_place_rating_snapshot_at_or_before(
            place_id=matched_business["place_id"],
            recorded_at=previous_cutoff,
        )
        report = build_rating_drop_report(
            current_snapshot=current_snapshot,
            previous_snapshot=previous_snapshot,
            report_frequency=report_frequency,
            previous_cutoff=previous_cutoff,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GooglePlacesError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {
        "user_id": user_id,
        "business_name": matched_business.get("business_name") or business_name,
        "location": (
            matched_business.get("business_address")
            or matched_business.get("input_address")
            or location
        ),
        "place_id": matched_business.get("place_id"),
        **report,
    }


@router.get("/management/details")
@router.get("/management/detail")
async def business_management_detail(
    request: Request,
    overlook: str,
    business_name: str | None = None,
    user_id: str | None = None,
):
    try:
        result = await build_business_management_detail(
            business_name=business_name,
            user_id=user_id,
            overlook=overlook,
            photo_url_builder=lambda reference: _photo_proxy_url(request, reference),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Business not found.",
        )

    return result

@router.get("/management/categories")
async def business_categories():
    return await build_business_categories()
