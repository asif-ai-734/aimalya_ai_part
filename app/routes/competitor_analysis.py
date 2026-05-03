from fastapi import APIRouter
from app.db.business_context_store import get_latest_business_context
from app.services import (
    place_loader,
    competitor_loader,
    competitor_analysis,
    competitor_ai_service
)

router = APIRouter(prefix="/competitors", tags=["Competitor Analysis"])


@router.get("/analysis")
async def competitor_report(place_id: str | None = None):
    place_data = await place_loader.load_place_data(place_id)
    context = await get_latest_business_context(place_id)
    my = place_data

    my_rating = my.get("rating", 0)
    my_price_level = my.get("price_level", 2)

    # YOUR BUSINESS (derive from DB/JSON instead of hard-coded values)
    my_business = {
        "name": my.get("name", "My Business"),
        "rating": my_rating,
        "reviews": my.get("user_ratings_total", 0),
        "sentiment": round((my_rating / 5) * 100) if my_rating else 0,
        "response_rate": round(50 + (my_rating * 5)) if my_rating else 0,
        "criteria": competitor_analysis.estimate_criteria_scores(
            my_rating, my_price_level
        ),
    }

    competitors = await competitor_loader.load_competitors_from_db(place_id)

    competitor_businesses = []
    for c in competitors:
        rating = c.get("rating", 0)
        competitor_businesses.append(
            {
                "name": c.get("name", "Unknown"),
                "rating": rating,
                "reviews": c.get("reviews", 0),
                "sentiment": round((rating / 5) * 100) if rating else 0,
                "response_rate": round(50 + (rating * 5)) if rating else 0,
                "criteria": competitor_analysis.estimate_criteria_scores(
                    rating, c.get("price_level", 2)
                ),
            }
        )

    businesses = [my_business] + competitor_businesses

    performance = competitor_analysis.build_performance_comparison(businesses)
    radar = competitor_analysis.build_category_radar(businesses)
    criteria = competitor_analysis.build_criteria_comparison(
        businesses, my_business["name"]
    )
    competitors_excel, my_advantages = (
        competitor_analysis.extract_advantages(criteria, my_business["name"])
    )

    business_goals = context.get("goals", []) if context else []
    report_frequency = context.get("report_frequency") if context else None

    ai = await competitor_ai_service.generate_competitive_strategy({
        "my_business": my_business,
        "competitors": competitor_businesses,
        "criteria_comparison": criteria,
        "business_goals": business_goals,
        "report_frequency": report_frequency,
    })

    return {
        "business_goals": business_goals,
        "report_frequency": report_frequency,
        "cards": businesses,
        "performance_comparison": performance,
        "category_radar": radar,
        "criteria_comparison": criteria,
        "competitors_excel": competitors_excel,
        "my_advantages": my_advantages,
        "strategic_recommendations": ai
    }
