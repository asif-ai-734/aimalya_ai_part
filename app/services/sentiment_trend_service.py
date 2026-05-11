#app.services.sentiment_trand_service.py
from datetime import date, datetime


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _review_month(review: dict) -> date | None:
    timestamp = review.get("time")
    if timestamp is None:
        return None

    try:
        return _month_start(datetime.fromtimestamp(int(timestamp)).date())
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _empty_last_year_trend(today: date) -> dict[date, dict]:
    end_month = _month_start(today)
    start_month = _add_months(end_month, -11)

    return {
        _add_months(start_month, index): {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
        }
        for index in range(12)
    }


def build_sentiment_trend(
    reviews: list,
    analyzed_reviews: list,
    today: date | None = None,
):
    trend = _empty_last_year_trend(today or date.today())

    for r, ar in zip(reviews, analyzed_reviews):
        month = _review_month(r)
        if month not in trend:
            continue

        sentiment = ar["sentiment"]

        if sentiment == "Positive":
            trend[month]["positive"] += 1
        elif sentiment == "Neutral":
            trend[month]["neutral"] += 1
        else:
            trend[month]["negative"] += 1

    return [
        {"period": month.strftime("%B"), **counts}
        for month, counts in trend.items()
    ]
