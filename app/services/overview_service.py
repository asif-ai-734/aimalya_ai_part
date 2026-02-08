#app.services.overview_service.py

from app.services.dashboard_analysis import analyze_reviews


def build_overview(place_data: dict, analysis: dict):
    return {
        "overall_rating": place_data.get("rating"),
        "review_volume": place_data.get("user_ratings_total"),
        "response_rate": 68,
        "satisfaction_index": analysis["satisfaction_index"],
        "key_strengths": [
            {"strength": k, "mentions": v}
            for k, v in analysis["key_strengths"]
        ],
        "key_issues": [
            {"issue": k, "mentions": v}
            for k, v in analysis["key_issues"]
        ]
    }
