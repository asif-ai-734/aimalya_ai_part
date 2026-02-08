#app.services.dashboard_analysis.py

from collections import Counter
from app.services.gemini_client import analyze_review_with_gemini


def analyze_reviews(reviews: list):
    sentiment_count = {"Positive": 0, "Neutral": 0, "Negative": 0}
    strengths = Counter()
    issues = Counter()
    analyzed_reviews = []

    for r in reviews:
        result = analyze_review_with_gemini(r["text"])

        sentiment = result["sentiment"]
        strengths_phrases = result.get("strengths", [])
        issues_phrases = result.get("issues", [])

        sentiment_count[sentiment] += 1
        analyzed_reviews.append(result)

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
