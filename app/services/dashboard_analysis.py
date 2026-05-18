#app.services.dashboard_analysis.py

import asyncio
from collections import Counter
from app.services.openai_analysis_client import analyze_review_with_openai


OPENAI_REVIEW_CONCURRENCY = 5
NO_ISSUE_FALLBACK = "No Issue found"


async def _analyze_review(review: dict, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        return await analyze_review_with_openai(review.get("text", ""))


def _review_rating(review: dict) -> float | None:
    try:
        return float(review.get("rating"))
    except (TypeError, ValueError):
        return None


def _normalize_sentiment(sentiment: str) -> str:
    normalized = str(sentiment or "Neutral").capitalize()
    return normalized if normalized in {"Positive", "Neutral", "Negative"} else "Neutral"


def _rating_adjusted_sentiment(review: dict, sentiment: str) -> str:
    sentiment = _normalize_sentiment(sentiment)
    rating = _review_rating(review)

    if rating is None:
        return sentiment
    if rating <= 2:
        return "Negative"
    if rating <= 3 and sentiment == "Positive":
        return "Neutral"

    return sentiment


async def analyze_reviews(reviews: list):
    sentiment_count = {"Positive": 0, "Neutral": 0, "Negative": 0}
    strengths = Counter()
    issues = Counter()
    semaphore = asyncio.Semaphore(OPENAI_REVIEW_CONCURRENCY)
    analyzed_reviews = await asyncio.gather(
        *(_analyze_review(review, semaphore) for review in reviews)
    )

    for review, result in zip(reviews, analyzed_reviews):
        sentiment = _rating_adjusted_sentiment(review, result.get("sentiment"))
        strengths_phrases = result.get("strengths", [])
        issues_phrases = result.get("issues", [])

        result["sentiment"] = sentiment
        result["issues"] = issues_phrases
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
        "key_issues": issues.most_common(5) or [(NO_ISSUE_FALLBACK, 0)],
        "reviews_analysis": analyzed_reviews
    }


def build_sentiment_summary(reviews_analysis: list):
    from collections import Counter
    return dict(Counter(r["sentiment"] for r in reviews_analysis))
