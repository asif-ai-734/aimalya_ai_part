# app.routes.monthly_report.py

import asyncio
from collections import Counter
from datetime import date

from fastapi import APIRouter, HTTPException

from app.db.business_context_store import get_latest_business_context

from app.services import (
    place_loader,
    dashboard_analysis,
    monthly_report_service,
    monthly_report_ai_service,
)
from app.services.business_lookup import find_user_business

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/monthly")
async def monthly_report(
    user_id: str = "user_123",
    business_name: str = "Softvence Ltd",
    report_frequency: str = "monthly",
    start_date: date = date(2026, 5, 1),
    end_date: date = date(2026, 5, 31),
    address: str | None = "Dhaka, Bangladesh",
):
    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="end_date must be on or after start_date.",
        )

    try:
        normalized_frequency = monthly_report_service.normalize_report_frequency(
            report_frequency
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    all_reviews = place_data.get("reviews", [])
    reviews = monthly_report_service.filter_reviews_by_date(
        all_reviews,
        start_date=start_date,
        end_date=end_date,
    )

    analysis = await dashboard_analysis.analyze_reviews(reviews)
    kpis = monthly_report_service.build_report_kpis(reviews, analysis)

    sentiment_counter = Counter(
        r["sentiment"] for r in analysis["reviews_analysis"]
    )

    ai_summary = await monthly_report_ai_service.generate_monthly_ai_summary(
        {
            "reviews_count": len(reviews),
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "sentiments": dict(sentiment_counter),
            "kpis": kpis,
            "total_reviews_available": len(all_reviews),
            "business_goals": context.get("goals", []) if context else [],
            "report_frequency": normalized_frequency,
            "requested_report_frequency": report_frequency,
        }
    )

    report = monthly_report_service.build_monthly_report(
        reviews,
        analysis,
        kpis,
        ai_summary,
        report_frequency=normalized_frequency,
        start_date=start_date,
        end_date=end_date,
        total_reviews_available=len(all_reviews),
    )

    report["business_goals"] = context.get("goals", []) if context else []
    report["saved_report_frequency"] = (
        context.get("report_frequency") if context else None
    )

    return report

