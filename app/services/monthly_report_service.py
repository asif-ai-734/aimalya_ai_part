#app.services.monthly_report_service.py
from collections import Counter
from statistics import mean
from datetime import datetime


def build_monthly_report(
    reviews: list,
    analysis: dict,
    previous_kpis: dict,
    ai_summary: dict
):
    ratings = []
    sentiment_counter = Counter()
    strengths_counter = Counter()
    issues_counter = Counter()

    weekly_reviews = {1: [], 2: [], 3: [], 4: []}

    for review, ar in zip(reviews, analysis["reviews_analysis"]):
        ratings.append(review["rating"])
        sentiment_counter[ar["sentiment"]] += 1

        for s in ar.get("strengths", []):
            strengths_counter[s] += 1
        for i in ar.get("issues", []):
            issues_counter[i] += 1

        week = min((datetime.fromtimestamp(review["time"]).day - 1) // 7 + 1, 4)
        weekly_reviews[week].append(review["rating"])

    total_reviews = len(reviews)
    avg_rating = round(mean(ratings), 1) if ratings else 0

    sentiment_breakdown = {
        "positive": {
            "percent": round((sentiment_counter["Positive"] / total_reviews) * 100),
            "count": sentiment_counter["Positive"]
        },
        "neutral": {
            "percent": round((sentiment_counter["Neutral"] / total_reviews) * 100),
            "count": sentiment_counter["Neutral"]
        },
        "negative": {
            "percent": round((sentiment_counter["Negative"] / total_reviews) * 100),
            "count": sentiment_counter["Negative"]
        }
    }

    return {
        "report_title": f"{datetime.utcnow().strftime('%B %Y')} Monthly Report",
        "period": (datetime.utcnow().replace(day=1)).strftime("%B %Y"),

        "kpis": previous_kpis,
        "executive_summary": ai_summary["executive_summary"],

        "review_volume_trend": [
            {"week": f"Week {w}", "count": len(weekly_reviews[w])}
            for w in weekly_reviews
        ],
        "rating_trend": [
            {
                "week": f"Week {w}",
                "rating": round(mean(weekly_reviews[w]), 1)
                if weekly_reviews[w] else avg_rating
            }
            for w in weekly_reviews
        ],

        "sentiment_breakdown": sentiment_breakdown,

        "top_complaints": [
            {"issue": k, "mentions": v}
            for k, v in issues_counter.most_common(3)
        ],

        "top_praises": [
            {"strength": k, "mentions": v}
            for k, v in strengths_counter.most_common(3)
        ],

        "ai_recommendations": ai_summary["recommendations"],
        "action_plan": ai_summary["action_plan"]
    }
