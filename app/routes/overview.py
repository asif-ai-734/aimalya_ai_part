#app.routes.overview.py

from fastapi import APIRouter
from app.services import (
    place_loader,
    overview_service,
    sentiment_trend_service,
    dashboard_analysis,
    criteria_service
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview")
def overview_dashboard():
    place_data = place_loader.load_place_data()
    reviews = place_data.get("reviews", [])

    # 1️⃣ Analyze reviews ONCE (Gemini already inside)
    analysis = dashboard_analysis.analyze_reviews(reviews)

    # 2️⃣ Build sections
    overview = overview_service.build_overview(place_data, analysis)
    sentiment_trend = sentiment_trend_service.build_sentiment_trend(
        reviews,
        analysis["reviews_analysis"]
    )
    performance_criteria = criteria_service.aggregate_criteria_scores(
        analysis["reviews_analysis"]
    )

    return {
        "overview": overview,
        "sentiment_trend": sentiment_trend,
        "performance_criteria": performance_criteria
    }
