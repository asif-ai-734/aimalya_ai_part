from datetime import datetime, timedelta
from collections import Counter


def _review_datetime(review: dict) -> datetime | None:
    timestamp = review.get("time")
    if timestamp is None:
        return None

    try:
        return datetime.fromtimestamp(int(timestamp))
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _trend_items(current: Counter) -> list[dict]:
    return [
        {
            "trend": trend,
            "mentions": mentions,
        }
        for trend, mentions in current.most_common(5)
    ]


def extract_emerging_and_declining(reviews: list, analyzed_reviews: list):
    """
    Detect emerging strengths and declining issues
    using review timestamps (last 30 days)
    """
    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=30)

    strengths_counter = Counter()
    issues_counter = Counter()

    for review, analysis in zip(reviews, analyzed_reviews):
        review_date = _review_datetime(review)
        if not review_date:
            continue

        if review_date >= recent_cutoff:
            for s in analysis.get("strengths", []):
                strengths_counter[s] += 1

            for i in analysis.get("issues", []):
                issues_counter[i] += 1

    emerging = _trend_items(strengths_counter)
    declining = _trend_items(issues_counter)

    return emerging, declining
