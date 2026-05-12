from fastapi import APIRouter, HTTPException

from app.services.business_management_service import (
    build_business_management,
    build_business_management_detail,
)


router = APIRouter(prefix="/businesses", tags=["Business Management"])


@router.get("/management")
async def business_management(user_id: str):
    return await build_business_management(user_id)


@router.get("/management/detail")
async def business_management_detail(
    user_id: str,
    business_name: str,
    overlook: str,
):
    try:
        result = await build_business_management_detail(
            user_id=user_id,
            business_name=business_name,
            overlook=overlook,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Business not found for this user.",
        )

    return result
