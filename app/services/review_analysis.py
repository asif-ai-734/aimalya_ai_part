from statistics import mean
from collections import Counter
from datetime import datetime
from app.services.gemini_client import analyze_review_with_gemini


async def build_reviews_analysis_page(reviews: list):
    ratings = []
    sentiment_counter = Counter()
    emotion_counter = Counter()
    keyword_counter = Counter()
    analyzed_reviews = []

    for r in reviews:
        ratings.append(r["rating"])

        ai = await analyze_review_with_gemini(r["text"])

        sentiment_counter[ai["sentiment"]] += 1

        for e in ai.get("emotions", []):
            emotion_counter[e] += 1

        for k in ai.get("keywords", []):
            keyword_counter[k.lower()] += 1

        analyzed_reviews.append({
            "author": r["author_name"],
            "rating": r["rating"],
            "date": datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d"),
            "text": r["text"],

            # AI output
            "sentiment": ai["sentiment"],
            "emotions": ai["emotions"],
            "strengths": ai["strengths"],
            "issues": ai["issues"],
            "keywords": ai["keywords"],
            "criteria_scores": ai["criteria_scores"],

            # future
            "replied": False
        })

    avg_rating = round(mean(ratings), 1) if ratings else 0.0

    return {
        "stats": {
            "total_reviews": len(reviews),
            "avg_rating": avg_rating,
            "sentiments": sentiment_counter,
            "emotions": emotion_counter
        },
        "top_keywords": [
            {"keyword": k, "mentions": v}
            for k, v in keyword_counter.most_common(10)
        ],
        "reviews": analyzed_reviews
    }
