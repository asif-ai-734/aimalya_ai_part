#app.services.monthly_report_service.py
from collections import Counter
from statistics import mean
from datetime import date, datetime, timedelta


SUPPORTED_REPORT_FREQUENCIES = {
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
}


def normalize_report_frequency(report_frequency: str) -> str:
    normalized = report_frequency.strip().casefold().replace("_", "-")
    aliases = {
        "day": "daily",
        "daily": "daily",
        "week": "weekly",
        "weekly": "weekly",
        "month": "monthly",
        "monthly": "monthly",
        "quarter": "quarterly",
        "quarterly": "quarterly",
        "year": "yearly",
        "yearly": "yearly",
        "annual": "yearly",
        "annually": "yearly",
    }
    frequency = aliases.get(normalized)
    if not frequency:
        supported = ", ".join(sorted(SUPPORTED_REPORT_FREQUENCIES))
        raise ValueError(f"report_frequency must be one of: {supported}.")
    return frequency


def _review_date(review: dict) -> date | None:
    timestamp = review.get("time")
    if timestamp is None:
        return None

    try:
        return datetime.fromtimestamp(int(timestamp)).date()
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def filter_reviews_by_date(
    reviews: list[dict],
    *,
    start_date: date,
    end_date: date,
) -> list[dict]:
    return [
        review
        for review in reviews
        if (review_date := _review_date(review))
        and start_date <= review_date <= end_date
    ]


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _quarter_start(value: date) -> date:
    month = ((value.month - 1) // 3) * 3 + 1
    return date(value.year, month, 1)


def _period_start(
    value: date,
    *,
    frequency: str,
    report_start: date,
) -> date:
    if frequency == "daily":
        return value
    if frequency == "weekly":
        days_since_start = (value - report_start).days
        return report_start + timedelta(days=(days_since_start // 7) * 7)
    if frequency == "monthly":
        return date(value.year, value.month, 1)
    if frequency == "quarterly":
        return _quarter_start(value)
    return date(value.year, 1, 1)


def _next_period_start(value: date, frequency: str) -> date:
    if frequency == "daily":
        return value + timedelta(days=1)
    if frequency == "weekly":
        return value + timedelta(days=7)
    if frequency == "monthly":
        return _add_months(value, 1)
    if frequency == "quarterly":
        return _add_months(value, 3)
    return date(value.year + 1, 1, 1)


def _period_label(
    value: date,
    *,
    frequency: str,
    report_end: date,
) -> str:
    if frequency == "daily":
        return value.isoformat()
    if frequency == "weekly":
        period_end = min(value + timedelta(days=6), report_end)
        return f"{value.isoformat()} to {period_end.isoformat()}"
    if frequency == "monthly":
        return value.strftime("%B %Y")
    if frequency == "quarterly":
        quarter = ((value.month - 1) // 3) + 1
        return f"Q{quarter} {value.year}"
    return str(value.year)


def _empty_period_buckets(
    *,
    frequency: str,
    start_date: date,
    end_date: date,
) -> dict[date, list[dict]]:
    first_period = _period_start(
        start_date,
        frequency=frequency,
        report_start=start_date,
    )
    buckets = {}
    current = first_period

    while current <= end_date:
        buckets[current] = []
        current = _next_period_start(current, frequency)

    return buckets


def _period_buckets(
    reviews: list[dict],
    *,
    frequency: str,
    start_date: date,
    end_date: date,
) -> dict[date, list[dict]]:
    buckets = _empty_period_buckets(
        frequency=frequency,
        start_date=start_date,
        end_date=end_date,
    )

    for review in reviews:
        review_date = _review_date(review)
        if not review_date:
            continue

        period = _period_start(
            review_date,
            frequency=frequency,
            report_start=start_date,
        )
        buckets.setdefault(period, []).append(review)

    return dict(sorted(buckets.items()))


def _average_rating(reviews: list[dict], default: float | int = 0) -> float | int:
    ratings = [
        review["rating"]
        for review in reviews
        if review.get("rating") is not None
    ]
    return round(mean(ratings), 1) if ratings else default


def build_report_kpis(reviews: list[dict], analysis: dict) -> dict:
    avg_rating = _average_rating(reviews)
    total_reviews = len(reviews)

    return {
        "avg_rating": {"value": avg_rating, "change": None},
        "reviews": {"value": total_reviews, "change": None},
        "satisfaction": {
            "value": analysis.get("satisfaction_index", 0),
            "change": None,
        },
        "response_rate": {"value": None, "change": None},
    }


def build_monthly_report(
    reviews: list,
    analysis: dict,
    kpis: dict,
    ai_summary: dict,
    *,
    report_frequency: str,
    start_date: date,
    end_date: date,
    total_reviews_available: int | None = None,
):
    sentiment_counter = Counter()
    strengths_counter = Counter()
    issues_counter = Counter()

    for review, ar in zip(reviews, analysis["reviews_analysis"]):
        sentiment_counter[ar["sentiment"]] += 1

        for s in ar.get("strengths", []):
            strengths_counter[s] += 1
        for i in ar.get("issues", []):
            issues_counter[i] += 1

    total_reviews = len(reviews)
    avg_rating = _average_rating(reviews)
    period_buckets = _period_buckets(
        reviews,
        frequency=report_frequency,
        start_date=start_date,
        end_date=end_date,
    )

    def percent(count: int) -> int:
        if not total_reviews:
            return 0
        return round((count / total_reviews) * 100)

    sentiment_breakdown = {
        "positive": {
            "percent": percent(sentiment_counter["Positive"]),
            "count": sentiment_counter["Positive"]
        },
        "neutral": {
            "percent": percent(sentiment_counter["Neutral"]),
            "count": sentiment_counter["Neutral"]
        },
        "negative": {
            "percent": percent(sentiment_counter["Negative"]),
            "count": sentiment_counter["Negative"]
        }
    }

    return {
        "report_title": (
            f"{report_frequency.title()} Report: "
            f"{start_date.isoformat()} to {end_date.isoformat()}"
        ),
        "period": f"{start_date.isoformat()} to {end_date.isoformat()}",
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "report_frequency": report_frequency,
        "reviews_in_period": total_reviews,
        "total_reviews_available": total_reviews_available,

        "kpis": kpis,
        "executive_summary": ai_summary["executive_summary"],

        "review_volume_trend": [
            {
                "period": _period_label(
                    period,
                    frequency=report_frequency,
                    report_end=end_date,
                ),
                "count": len(period_reviews),
            }
            for period, period_reviews in period_buckets.items()
        ],
        "rating_trend": [
            {
                "period": _period_label(
                    period,
                    frequency=report_frequency,
                    report_end=end_date,
                ),
                "rating": _average_rating(period_reviews, avg_rating),
            }
            for period, period_reviews in period_buckets.items()
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
