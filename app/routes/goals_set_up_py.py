# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException

from app.schemas.goals_set_up_py import GoalsSetupRequest
from app.services.goals_setup_service import (
    GoalsSetupError,
    fetch_and_save_goals_setup,
)
from app.utils.counting_route import CountingRoute


router = APIRouter(prefix="/goals_set_up_py", tags=["Goals Setup"], route_class=CountingRoute)


@router.post("")
async def goals_set_up_py(payload: GoalsSetupRequest):
    try:
        return await fetch_and_save_goals_setup(payload)
    except GoalsSetupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
