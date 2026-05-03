#app.routes.review_analysis.py
from fastapi import APIRouter
from app.services import place_loader
from app.services.review_analysis import build_reviews_analysis_page

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("/analysis")
async def reviews_analysis(place_id: str | None = None):
    place_data = await place_loader.load_place_data(place_id)
    reviews = place_data.get("reviews", [])
    return await build_reviews_analysis_page(reviews)
