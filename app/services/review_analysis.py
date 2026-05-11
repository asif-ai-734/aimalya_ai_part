import asyncio
from statistics import mean
from collections import Counter
from datetime import datetime
from app.services.gemini_client import analyze_review_with_gemini


GEMINI_REVIEW_CONCURRENCY = 5


async def _analyze_review(review: dict, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        return await analyze_review_with_gemini(review.get("text", ""))


async def build_reviews_analysis_page(reviews: list):
    ratings = []
    sentiment_counter = Counter()
    analyzed_reviews = []
    semaphore = asyncio.Semaphore(GEMINI_REVIEW_CONCURRENCY)
    ai_results = await asyncio.gather(
        *(_analyze_review(review, semaphore) for review in reviews)
    )

    for r, ai in zip(reviews, ai_results):
        ratings.append(r["rating"])

        sentiment_counter[ai["sentiment"]] += 1

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
            "criteria_scores": ai["criteria_scores"],

            # future
            "replied": False
        })

    avg_rating = round(mean(ratings), 1) if ratings else 0.0

    return {
        "stats": {
            "total_reviews": len(reviews),
            "avg_ratings": avg_rating,
            "Positive_sentiments": sentiment_counter["Positive"],
            "negetive_sentiments": sentiment_counter["Negative"],
        },
        "reviews": analyzed_reviews
    }
