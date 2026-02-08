#app.routes.monthly_report.py
from fastapi import APIRouter
from collections import Counter
from app.services import (
    place_loader,
    dashboard_analysis,
    monthly_report_service,
    monthly_report_ai_service
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/monthly")
async def monthly_report():
    place_data = await place_loader.load_place_data()
    reviews = place_data.get("reviews", [])

    analysis = await dashboard_analysis.analyze_reviews(reviews)

    # TEMP: static previous KPIs (replace with DB later)
    previous_kpis = {
        "avg_rating": {"value": 4.6, "change": "+0.2"},
        "reviews": {"value": 234, "change": "+18%"},
        "satisfaction": {"value": 87, "change": "+5%"},
        "response_rate": {"value": 68, "change": "-5%"}
    }

    sentiment_counter = Counter(
    r["sentiment"] for r in analysis["reviews_analysis"]
    )

    ai_summary = await monthly_report_ai_service.generate_monthly_ai_summary({
        "reviews_count": len(reviews),
        "sentiments": dict(sentiment_counter)
    })
    return monthly_report_service.build_monthly_report(
        reviews,
        analysis,
        previous_kpis,
        ai_summary
    )
