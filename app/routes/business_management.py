from fastapi import APIRouter, HTTPException

from app.services.business_management_service import (
    build_business_management,
    build_business_management_detail,
    build_business_categories,
)
from app.utils.counting_route import CountingRoute

router = APIRouter(prefix="/businesses", tags=["Business Management"], route_class=CountingRoute)


@router.get("/management")
async def business_management():
    return await build_business_management()


@router.get("/management/detail")
async def business_management_detail(
    business_name: str,
    overlook: str,
):
    try:
        result = await build_business_management_detail(
            business_name=business_name,
            overlook=overlook,
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