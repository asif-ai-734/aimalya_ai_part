#app.services.overview_service.py

from datetime import datetime, timezone


PERIOD_DAYS = 30
PERIOD_SECONDS = PERIOD_DAYS * 24 * 60 * 60


def _review_timestamp(review: dict) -> int | None:
    timestamp = review.get("time")
    if timestamp is None:
        return None

    try:
        return int(timestamp)
    except (TypeError, ValueError):
        return None


def _latest_review_timestamp(reviews: list[dict]) -> int:
    timestamps = [
        timestamp
        for review in reviews
        for timestamp in [_review_timestamp(review)]
        if timestamp is not None
    ]
    if timestamps:
        return max(timestamps)

    return int(datetime.now(timezone.utc).timestamp())


def _period_review_pairs(
    reviews: list[dict],
    reviews_analysis: list[dict],
) -> tuple[list[tuple[dict, dict]], list[tuple[dict, dict]]]:
    latest_timestamp = _latest_review_timestamp(reviews)
    current_start = latest_timestamp - PERIOD_SECONDS
    previous_start = current_start - PERIOD_SECONDS

    current_pairs = []
    previous_pairs = []

    for review, review_analysis in zip(reviews, reviews_analysis):
        timestamp = _review_timestamp(review)
        if timestamp is None:
            continue

        pair = (review, review_analysis)
        if current_start < timestamp <= latest_timestamp:
            current_pairs.append(pair)
        elif previous_start < timestamp <= current_start:
            previous_pairs.append(pair)

    return current_pairs, previous_pairs


def _average_review_rating(review_pairs: list[tuple[dict, dict]]) -> float | None:
    ratings = []
    for review, _ in review_pairs:
        try:
            ratings.append(float(review.get("rating")))
        except (TypeError, ValueError):
            continue

    if not ratings:
        return None

    return sum(ratings) / len(ratings)


def _satisfaction_index(review_pairs: list[tuple[dict, dict]]) -> int | None:
    if not review_pairs:
        return None

    sentiment_count = {"Positive": 0, "Neutral": 0, "Negative": 0}
    for _, review_analysis in review_pairs:
        sentiment = str(review_analysis.get("sentiment") or "Neutral").capitalize()
        if sentiment not in sentiment_count:
            sentiment = "Neutral"
        sentiment_count[sentiment] += 1

    total = max(sum(sentiment_count.values()), 1)
    return round(
        (
            (
                sentiment_count["Positive"]
                + sentiment_count["Neutral"] * 0.5
            )
            / total
        )
        * 100
    )


def _criteria_scores(review_pairs: list[tuple[dict, dict]]) -> dict[str, float]:
    bucket: dict[str, list[float]] = {}
    for _, review_analysis in review_pairs:
        for criteria, score in review_analysis.get("criteria_scores", {}).items():
            try:
                numeric_score = float(score)
            except (TypeError, ValueError):
                continue
            bucket.setdefault(criteria, []).append(numeric_score)

    return {
        criteria: sum(scores) / len(scores)
        for criteria, scores in bucket.items()
        if scores
    }


def _percent_change(current: float, previous: float | None) -> float | None:
    if previous in (None, 0):
        return None

    return round(((current - previous) / previous) * 100, 1)


def _growth_metric(
    current: float | int | None,
    previous: float | int | None,
    *,
    unit: str,
    decimals: int,
    suffix: str = "",
) -> dict:
    current_value = 0 if current is None else current
    previous_value = current_value if previous is None else previous
    raw_delta = current_value - previous_value
    delta = round(raw_delta, decimals)
    if decimals == 0:
        delta = int(delta)

    sign = "+" if delta >= 0 else ""
    display = f"{sign}{delta}{suffix}"
    percent_change = _percent_change(float(current_value), previous)
    percent_display = None
    if percent_change is not None:
        percent_sign = "+" if percent_change >= 0 else ""
        percent_display = f"{percent_sign}{percent_change}%"
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"

    return {
        "value": delta,
        "display": display,
        "unit": unit,
        "direction": direction,
        "label": f"{display} vs last month",
        "percent_change": percent_change,
        "percent_display": percent_display,
    }


def build_growth_metrics(reviews: list[dict], analysis: dict) -> dict:
    reviews_analysis = analysis.get("reviews_analysis", [])
    current_pairs, previous_pairs = _period_review_pairs(
        reviews,
        reviews_analysis,
    )

    current_rating = _average_review_rating(current_pairs)
    previous_rating = _average_review_rating(previous_pairs)
    current_satisfaction = _satisfaction_index(current_pairs)
    previous_satisfaction = _satisfaction_index(previous_pairs)

    return {
        "overall_rating": _growth_metric(
            current_rating,
            previous_rating,
            unit="points",
            decimals=1,
        ),
        "satisfaction_index": _growth_metric(
            current_satisfaction,
            previous_satisfaction,
            unit="percent",
            decimals=0,
            suffix="%",
        ),
        "review_volume": _growth_metric(
            len(current_pairs),
            len(previous_pairs),
            unit="count",
            decimals=0,
        ),
    }


def build_performance_criteria_growth(
    reviews: list[dict],
    reviews_analysis: list[dict],
    current_scores: dict[str, float],
) -> dict[str, dict]:
    current_pairs, previous_pairs = _period_review_pairs(
        reviews,
        reviews_analysis,
    )
    current_period_scores = _criteria_scores(current_pairs)
    previous_period_scores = _criteria_scores(previous_pairs)

    return {
        criteria: _growth_metric(
            current_period_scores.get(criteria, current_score),
            previous_period_scores.get(criteria),
            unit="points",
            decimals=1,
        )
        for criteria, current_score in current_scores.items()
    }


def build_performance_criteria_with_growth(
    current_scores: dict[str, float],
    growth: dict[str, dict],
) -> dict[str, dict]:
    return {
        criteria: {
            "score": score,
            "growth": growth.get(criteria),
        }
        for criteria, score in current_scores.items()
    }


def build_overview(
    place_data: dict,
    analysis: dict,
    reviews: list[dict] | None = None,
):
    reviews = reviews or []
    return {
        "overall_rating": place_data.get("rating"),
        "review_volume": place_data.get("user_ratings_total"),
        "response_rate": 68,
        "satisfaction_index": analysis["satisfaction_index"],
        "growth": build_growth_metrics(reviews, analysis),
        "key_strengths": [
            {"strength": k, "mentions": v}
            for k, v in analysis["key_strengths"]
        ],
        "key_issues": [
            {"issue": k, "mentions": v}
            for k, v in analysis["key_issues"]
        ],
    }
