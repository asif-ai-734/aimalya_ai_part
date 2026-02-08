from datetime import datetime, timedelta
from collections import Counter


def extract_emerging_and_declining(reviews: list, analyzed_reviews: list):
    """
    Detect emerging strengths and declining issues
    using review timestamps (last 30 days)
    """
    recent_cutoff = datetime.utcnow() - timedelta(days=30)

    strengths_counter = Counter()
    issues_counter = Counter()

    for review, analysis in zip(reviews, analyzed_reviews):
        review_date = datetime.fromtimestamp(review["time"])

        if review_date >= recent_cutoff:
            for s in analysis.get("strengths", []):
                strengths_counter[s] += 1

            for i in analysis.get("issues", []):
                issues_counter[i] += 1

    emerging = [
        {"trend": k, "mentions": v}
        for k, v in strengths_counter.most_common(5)
    ]

    declining = [
        {"trend": k, "mentions": v}
        for k, v in issues_counter.most_common(5)
    ]

    return emerging, declining
