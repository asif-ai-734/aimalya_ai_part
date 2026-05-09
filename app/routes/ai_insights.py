#app.routes.ai_insights.py

from fastapi import APIRouter, HTTPException

from app.db.business_context_store import get_latest_business_context
from app.db.business_store import get_user_businesses

from app.services import (
    place_loader,
    overview_service,
    criteria_service,
    dashboard_analysis,
    insights_aggregation_service,
    ai_insights_service,
)

router = APIRouter(prefix="/insights", tags=["AI Insights"])


@router.get("/recommendations")
async def ai_insights(
    user_id: str,
    business_name: str,
    address: str | None = None,
):
    businesses = await get_user_businesses(user_id)

    matched_business = None

    for business in businesses:
        name_matches = (
            business.get("business_name", "").strip().casefold()
            == business_name.strip().casefold()
        )

        address_matches = True

        if address:
            saved_address = (
                business.get("business_address")
                or business.get("input_address")
                or ""
            )

            address_matches = (
                address.strip().casefold()
                in saved_address.strip().casefold()
            )

        if name_matches and address_matches:
            matched_business = business
            break

    if not matched_business:
        raise HTTPException(
            status_code=404,
            detail="Business not found for this user.",
        )

    place_id = matched_business["place_id"]

    place_data = await place_loader.load_place_data(
        place_id,
        user_id=user_id,
    )

    context = await get_latest_business_context(
        place_id,
        user_id=user_id,
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
    report_frequency = context.get("report_frequency") if context else None

    insights_input = {
        "overview": overview,
        "performance_by_category": performance_by_category,
        "emerging_trends": emerging,
        "declining_areas": declining,
        "business_goals": business_goals,
        "report_frequency": report_frequency,
    }

    ai_insights = await ai_insights_service.generate_ai_insights(insights_input)

    return {
        **ai_insights,
        "performance_by_category": performance_by_category,
        "emerging_trends": emerging,
        "declining_areas": declining,
        "business_goals": business_goals,
        "report_frequency": report_frequency,
    }




# from fastapi import APIRouter
# from app.db.business_context_store import get_latest_business_context
# from app.services import (
#     place_loader,
#     overview_service,
#     criteria_service,
#     dashboard_analysis,
#     insights_aggregation_service,
#     ai_insights_service
# )

# router = APIRouter(prefix="/insights", tags=["AI Insights"])


# @router.get("/recommendations")
# async def ai_insights(
#     place_id: str | None = None,
#     user_id: str | None = None,
# ):
#     place_data = await place_loader.load_place_data(place_id, user_id=user_id)
#     context = await get_latest_business_context(place_id, user_id=user_id)
#     reviews = place_data.get("reviews", [])

#     analysis = await dashboard_analysis.analyze_reviews(reviews)

#     overview = overview_service.build_overview(place_data, analysis)

#     raw_criteria = criteria_service.aggregate_criteria_scores(
#         analysis["reviews_analysis"]
#     )

#     # 🔹 Performance by Category
#     performance_by_category = criteria_service.normalize_criteria_scores(
#         raw_criteria
#     )

#     emerging, declining = insights_aggregation_service.extract_emerging_and_declining(
#     reviews,
#     analysis["reviews_analysis"]
#     )
#     business_goals = context.get("goals", []) if context else []
#     report_frequency = context.get("report_frequency") if context else None

#     insights_input = {
#         "overview": overview,
#         "performance_by_category": performance_by_category,
#         "emerging_trends": emerging,
#         "declining_areas": declining,
#         "business_goals": business_goals,
#         "report_frequency": report_frequency,
#     }

#     ai_insights = await ai_insights_service.generate_ai_insights(insights_input)

#     return {
#         **ai_insights,
#         "performance_by_category": performance_by_category,
#         "emerging_trends": emerging,
#         "declining_areas": declining,
#         "business_goals": business_goals,
#         "report_frequency": report_frequency,
#     }
