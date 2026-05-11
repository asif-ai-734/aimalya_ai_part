#app.routes.ai_insights.py

import asyncio

from fastapi import APIRouter, HTTPException

from app.db.business_context_store import get_latest_business_context

from app.services import (
    place_loader,
    overview_service,
    criteria_service,
    dashboard_analysis,
    insights_aggregation_service,
    ai_insights_service,
)
from app.services.business_lookup import find_user_business

router = APIRouter(prefix="/insights", tags=["AI Insights"])


ACTIONABLE_RECOMMENDATION_STYLES = [
    {
        "type": "staff_training",
        "title": "Staff Training",
        "description": (
            "Improve guest handling, response quality, and service consistency "
            "through focused staff coaching."
        ),
    },
    {
        "type": "operations_consulting",
        "title": "Operations Consulting",
        "description": (
            "Review daily workflows, bottlenecks, and service processes to "
            "improve speed and customer experience."
        ),
    },
    {
        "type": "performance_program",
        "title": "Performance Program",
        "description": (
            "Track review trends, team performance, and customer satisfaction "
            "with a structured improvement program."
        ),
    },
]


def _business_picture(place_data: dict) -> dict | None:
    photos = place_data.get("photos") or []
    if not photos:
        return None

    photo = photos[0]
    return {
        "photo_reference": photo.get("photo_reference"),
        "width": photo.get("width"),
        "height": photo.get("height"),
        "html_attributions": photo.get("html_attributions") or [],
    }


@router.get("/recommendations")
async def ai_insights(
    user_id: str,
    business_name: str,
    address: str | None = None,
):
    matched_business = await find_user_business(
        user_id=user_id,
        business_name=business_name,
        address=address,
    )

    if not matched_business:
        raise HTTPException(
            status_code=404,
            detail="Business not found for this user.",
        )

    place_id = matched_business["place_id"]

    place_data, context = await asyncio.gather(
        place_loader.load_place_data(
            place_id,
            user_id=user_id,
        ),
        get_latest_business_context(
            place_id,
            user_id=user_id,
        ),
    )

    reviews = place_data.get("reviews", [])

    analysis = await dashboard_analysis.analyze_reviews(reviews)

    overview = overview_service.build_overview(place_data, analysis)

    raw_criteria = criteria_service.aggregate_criteria_scores(
        analysis["reviews_analysis"]
    )

    performance_by_category = criteria_service.normalize_criteria_scores(
        raw_criteria
    )

    emerging, declining = insights_aggregation_service.extract_emerging_and_declining(
        reviews,
        analysis["reviews_analysis"],
    )

    business_goals = context.get("goals", []) if context else []

    insights_input = {
        "overview": overview,
        "performance_by_category": performance_by_category,
        "detected_emerging_trends": emerging,
        "detected_declining_areas": declining,
        "business_goals": business_goals,
    }

    ai_insights = await ai_insights_service.generate_ai_insights(insights_input)

    return {
        **ai_insights,
        "business_picture": _business_picture(place_data),
        "performance_by_category": performance_by_category,
        "business_goals": business_goals,
        "actionable_recommendation_styles": ACTIONABLE_RECOMMENDATION_STYLES,
    }
