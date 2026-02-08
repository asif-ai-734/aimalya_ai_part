#app.routes.review_analysis.py
from fastapi import APIRouter
from app.services import place_loader
from app.services.review_analysis import build_reviews_analysis_page

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("/analysis")
def reviews_analysis():
    place_data = place_loader.load_place_data()
    reviews = place_data.get("reviews", [])
    return build_reviews_analysis_page(reviews)
