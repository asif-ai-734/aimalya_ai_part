from fastapi import APIRouter
from app.services import (
    place_loader,
    overview_service,
    criteria_service,
    criteria_service,
    dashboard_analysis,
    insights_aggregation_service,
    ai_insights_service
)

router = APIRouter(prefix="/insights", tags=["AI Insights"])


@router.get("/recommendations")
async def ai_insights():
    place_data = await place_loader.load_place_data()
    reviews = place_data.get("reviews", [])

    analysis = await dashboard_analysis.analyze_reviews(reviews)

    overview = overview_service.build_overview(place_data, analysis)

    raw_criteria = criteria_service.aggregate_criteria_scores(
        analysis["reviews_analysis"]
    )

    # 🔹 Performance by Category
    performance_by_category = criteria_service.normalize_criteria_scores(
        raw_criteria
    )

    emerging, declining = insights_aggregation_service.extract_emerging_and_declining(
    reviews,
    analysis["reviews_analysis"]
    )

    insights_input = {
        "overview": overview,
        "performance_by_category": performance_by_category,
        "emerging_trends": emerging,
        "declining_areas": declining
    }

    ai_insights = await ai_insights_service.generate_ai_insights(insights_input)

    return {
        **ai_insights,
        "performance_by_category": performance_by_category,
        "emerging_trends": emerging,
        "declining_areas": declining
    }
