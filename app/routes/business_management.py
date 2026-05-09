from fastapi import APIRouter

from app.services.business_management_service import build_business_management


router = APIRouter(prefix="/businesses", tags=["Business Management"])


@router.get("/management")
async def business_management(user_id: str):
    return await build_business_management(user_id)


@router.get("/management/{user_id}")
async def business_management_for_user(user_id: str):
    return await build_business_management(user_id)
