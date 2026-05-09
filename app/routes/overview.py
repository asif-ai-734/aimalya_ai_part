# app.routes.overview.py

from fastapi import APIRouter, HTTPException

from app.services import (
    place_loader,
    overview_service,
    sentiment_trend_service,
    dashboard_analysis,
    criteria_service,
)

from app.db.business_store import get_user_businesses


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview")
async def overview_dashboard(
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

    reviews = place_data.get("reviews", [])

    analysis = await dashboard_analysis.analyze_reviews(reviews)

    overview = overview_service.build_overview(
        place_data,
        analysis,
    )

    sentiment_trend = sentiment_trend_service.build_sentiment_trend(
        reviews,
        analysis["reviews_analysis"],
    )

    performance_criteria = criteria_service.aggregate_criteria_scores(
        analysis["reviews_analysis"]
    )

    return {
        "overview": overview,
        "sentiment_trend": sentiment_trend,
        "performance_criteria": performance_criteria,
    }




# #app.routes.overview.py

# from fastapi import APIRouter
# from app.services import (
#     place_loader,
#     overview_service,
#     sentiment_trend_service,
#     dashboard_analysis,
#     criteria_service
# )

# router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# @router.get("/overview")
# async def overview_dashboard(
#     place_id: str | None = None,
#     user_id: str | None = None,
# ):
#     place_data = await place_loader.load_place_data(place_id, user_id=user_id)
#     reviews = place_data.get("reviews", [])

#     # 1️⃣ Analyze reviews ONCE (Gemini already inside)
#     analysis = await dashboard_analysis.analyze_reviews(reviews)

#     # 2️⃣ Build sections
#     overview = overview_service.build_overview(place_data, analysis)
#     sentiment_trend = sentiment_trend_service.build_sentiment_trend(
#         reviews,
#         analysis["reviews_analysis"]
#     )
#     performance_criteria = criteria_service.aggregate_criteria_scores(
#         analysis["reviews_analysis"]
#     )

#     return {
#         "overview": overview,
#         "sentiment_trend": sentiment_trend,
#         "performance_criteria": performance_criteria
#     }
