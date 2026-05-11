#app.services.dashboard_analysis.py

import asyncio
from collections import Counter
from app.services.gemini_client import analyze_review_with_gemini


GEMINI_REVIEW_CONCURRENCY = 5


async def _analyze_review(review: dict, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        return await analyze_review_with_gemini(review.get("text", ""))


async def analyze_reviews(reviews: list):
    sentiment_count = {"Positive": 0, "Neutral": 0, "Negative": 0}
    strengths = Counter()
    issues = Counter()
    semaphore = asyncio.Semaphore(GEMINI_REVIEW_CONCURRENCY)
    analyzed_reviews = await asyncio.gather(
        *(_analyze_review(review, semaphore) for review in reviews)
    )

    for result in analyzed_reviews:
        sentiment = result["sentiment"]
        strengths_phrases = result.get("strengths", [])
        issues_phrases = result.get("issues", [])

        sentiment_count[sentiment] += 1

        for s in strengths_phrases:
            strengths[s] += 1
        for i in issues_phrases:
            issues[i] += 1

    total = max(sum(sentiment_count.values()), 1)

    satisfaction_index = round(
        ((sentiment_count["Positive"] +
          sentiment_count["Neutral"] * 0.5) / total) * 100
    )

    return {
        "satisfaction_index": satisfaction_index,
        "key_strengths": strengths.most_common(5),
        "key_issues": issues.most_common(5),
        "reviews_analysis": analyzed_reviews
    }


def build_sentiment_summary(reviews_analysis: list):
    from collections import Counter
    return dict(Counter(r["sentiment"] for r in reviews_analysis))
