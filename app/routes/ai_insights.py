#app.routes.ai_insights.py

import asyncio

from fastapi import APIRouter, HTTPException

from app.db.actionable_recommendation_store import (
    get_read_actionable_recommendation_title_keys,
    recommendation_title_key,
    save_actionable_recommendation_titles,
    update_actionable_recommendation_status as set_actionable_recommendation_status,
)
from app.db.business_context_store import get_latest_business_context
from app.schemas.ai_insights import ActionableRecommendationStatusUpdate

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


def _business_details(
    matched_business: dict,
    place_data: dict,
    context: dict | None,
    *,
    business_name: str,
    address: str | None,
) -> dict:
    return {
        "name": (
            matched_business.get("business_name")
            or place_data.get("name")
            or business_name
        ),
        "address": (
            matched_business.get("business_address")
            or matched_business.get("input_address")
            or place_data.get("formatted_address")
            or address
        ),
        "category": context.get("business_category") if context else None,
    }


def _recommendation_title(recommendation: dict) -> str:
    return str(recommendation.get("title") or "").strip()


async def _save_and_filter_unread_recommendations(
    *,
    user_id: str,
    payload: dict,
) -> dict:
    recommendations = payload.get("actionable_recommendations")
    if not isinstance(recommendations, list):
        return payload

    titles = [
        title
        for item in recommendations
        if isinstance(item, dict)
        for title in [_recommendation_title(item)]
        if title
    ]

    await save_actionable_recommendation_titles(
        user_id=user_id,
        titles=titles,
    )

    read_title_keys = await get_read_actionable_recommendation_title_keys(user_id)

    unread_recommendations = [
        recommendation
        for recommendation in recommendations
        if not isinstance(recommendation, dict)
        or recommendation_title_key(_recommendation_title(recommendation))
        not in read_title_keys
    ]

    return {
        **payload,
        "actionable_recommendations": unread_recommendations,
    }


async def _build_ai_insights_context(
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

    return {
        "matched_business": matched_business,
        "place_data": place_data,
        "context": context,
        "performance_by_category": performance_by_category,
        "business_goals": business_goals,
        "insights_input": insights_input,
    }


@router.get("/recommendations")
async def ai_insights(
    user_id: str,
    business_name: str,
    address: str | None = None,
):
    insights_context = await _build_ai_insights_context(
        user_id=user_id,
        business_name=business_name,
        address=address,
    )

    ai_insights = await ai_insights_service.generate_ai_insights(
        insights_context["insights_input"]
    )

    response = {
        **ai_insights,
        "business_picture": _business_picture(insights_context["place_data"]),
        "performance_by_category": insights_context["performance_by_category"],
        "business_goals": insights_context["business_goals"],
    }

    return await _save_and_filter_unread_recommendations(
        user_id=user_id,
        payload=response,
    )


@router.get("/actionable-recommendations")
async def ai_actionable_recommendations(
    user_id: str,
    business_name: str,
    address: str | None = None,
):
    insights_context = await _build_ai_insights_context(
        user_id=user_id,
        business_name=business_name,
        address=address,
    )

    recommendations_input = {
        **insights_context["insights_input"],
        "business": _business_details(
            insights_context["matched_business"],
            insights_context["place_data"],
            insights_context["context"],
            business_name=business_name,
            address=address,
        ),
    }

    recommendations = await ai_insights_service.generate_program_recommendations(
        recommendations_input
    )

    return await _save_and_filter_unread_recommendations(
        user_id=user_id,
        payload=recommendations,
    )


@router.patch("/actionable-recommendations/status")
async def update_actionable_recommendation_status(
    payload: ActionableRecommendationStatusUpdate,
):
    try:
        updated_recommendation = await set_actionable_recommendation_status(
            user_id=payload.user_id,
            title=payload.title,
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not updated_recommendation:
        raise HTTPException(
            status_code=404,
            detail="Actionable recommendation not found for this user.",
        )

    return {
        **updated_recommendation,
        "visible": updated_recommendation["status"] != "read",
    }
