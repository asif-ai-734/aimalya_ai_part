# app.routes.overview.py

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException

from app.services import (
    place_loader,
    overview_service,
    sentiment_trend_service,
    dashboard_analysis,
    criteria_service,
)

from app.services.business_lookup import find_user_business
from app.utils.counting_route import CountingRoute


router = APIRouter(prefix="/dashboard", tags=["Dashboard"], route_class=CountingRoute)



@router.get("/overview")
async def overview_dashboard(
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

    place_data = await place_loader.load_place_data(
        place_id,
        user_id=user_id,
    )

    reviews = place_data.get("reviews", [])

    analysis = await dashboard_analysis.analyze_reviews(reviews)

    overview = overview_service.build_overview(
        place_data,
        analysis,
        reviews,
    )

    sentiment_trend = sentiment_trend_service.build_sentiment_trend(
        reviews,
        analysis["reviews_analysis"],
    )

    performance_criteria = criteria_service.aggregate_criteria_scores(
        analysis["reviews_analysis"]
    )
    performance_criteria_growth = (
        overview_service.build_performance_criteria_growth(
            reviews,
            analysis["reviews_analysis"],
            performance_criteria,
        )
    )

    return {
        "overview": overview,
        "sentiment_trend": sentiment_trend,
        "performance_criteria": performance_criteria,
        "performance_criteria_growth": performance_criteria_growth,
        "performance_criteria_with_growth": (
            overview_service.build_performance_criteria_with_growth(
                performance_criteria,
                performance_criteria_growth,
            )
        ),
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

#     # Analyze reviews ONCE (OpenAI analysis already inside)
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
