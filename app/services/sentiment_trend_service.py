#app.services.sentiment_trand_service.py
from collections import defaultdict
from datetime import datetime


def build_sentiment_trend(reviews: list, analyzed_reviews: list):
    trend = defaultdict(lambda: {
        "positive": 0,
        "neutral": 0,
        "negative": 0
    })

    for r, ar in zip(reviews, analyzed_reviews):
        month = datetime.fromtimestamp(r["time"]).strftime("%Y-%m")
        sentiment = ar["sentiment"]

        if sentiment == "Positive":
            trend[month]["positive"] += 1
        elif sentiment == "Neutral":
            trend[month]["neutral"] += 1
        else:
            trend[month]["negative"] += 1

    return [
        {"period": month, **counts}
        for month, counts in sorted(trend.items())
    ]
