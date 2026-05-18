from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request

from app.services.business_management_service import (
    build_business_management,
    build_business_management_detail,
    build_business_categories,
    update_business_management_account_status,
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
            business_name=payload.business_name,
            action=payload.action,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Business not found.",
        )

    return result


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
