# app.routes.monthly_report.py

from fastapi import APIRouter, HTTPException
from collections import Counter

from app.db.business_context_store import get_latest_business_context
from app.db.business_store import get_user_businesses

from app.services import (
    place_loader,
    dashboard_analysis,
    monthly_report_service,
    monthly_report_ai_service,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/monthly")
async def monthly_report(
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

    previous_kpis = {
        "avg_rating": {"value": 4.6, "change": "+0.2"},
        "reviews": {"value": 234, "change": "+18%"},
        "satisfaction": {"value": 87, "change": "+5%"},
        "response_rate": {"value": 68, "change": "-5%"},
    }

    sentiment_counter = Counter(
        r["sentiment"] for r in analysis["reviews_analysis"]
    )

    ai_summary = await monthly_report_ai_service.generate_monthly_ai_summary(
        {
            "reviews_count": len(reviews),
            "sentiments": dict(sentiment_counter),
            "business_goals": context.get("goals", []) if context else [],
            "report_frequency": context.get("report_frequency") if context else None,
        }
    )

    report = monthly_report_service.build_monthly_report(
        reviews,
        analysis,
        previous_kpis,
        ai_summary,
    )

    report["business_goals"] = context.get("goals", []) if context else []
    report["report_frequency"] = context.get("report_frequency") if context else None

    return report


# #app.routes.monthly_report.py
# from fastapi import APIRouter
# from collections import Counter
# from app.db.business_context_store import get_latest_business_context
# from app.services import (
#     place_loader,
#     dashboard_analysis,
#     monthly_report_service,
#     monthly_report_ai_service
# )

# router = APIRouter(prefix="/reports", tags=["Reports"])


# @router.get("/monthly")
# async def monthly_report(
#     place_id: str | None = None,
#     user_id: str | None = None,
# ):
#     place_data = await place_loader.load_place_data(place_id, user_id=user_id)
#     context = await get_latest_business_context(place_id, user_id=user_id)
#     reviews = place_data.get("reviews", [])

#     analysis = await dashboard_analysis.analyze_reviews(reviews)

#     # TEMP: static previous KPIs (replace with DB later)
#     previous_kpis = {
#         "avg_rating": {"value": 4.6, "change": "+0.2"},
#         "reviews": {"value": 234, "change": "+18%"},
#         "satisfaction": {"value": 87, "change": "+5%"},
#         "response_rate": {"value": 68, "change": "-5%"}
#     }

#     sentiment_counter = Counter(
#     r["sentiment"] for r in analysis["reviews_analysis"]
#     )

#     ai_summary = await monthly_report_ai_service.generate_monthly_ai_summary({
#         "reviews_count": len(reviews),
#         "sentiments": dict(sentiment_counter),
#         "business_goals": context.get("goals", []) if context else [],
#         "report_frequency": context.get("report_frequency") if context else None,
#     })
#     report = monthly_report_service.build_monthly_report(
#         reviews,
#         analysis,
#         previous_kpis,
#         ai_summary
#     )
#     report["business_goals"] = context.get("goals", []) if context else []
#     report["report_frequency"] = (
#         context.get("report_frequency") if context else None
#     )
#     return report
