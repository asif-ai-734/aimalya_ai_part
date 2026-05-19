from datetime import datetime, timedelta
from typing import Any


def normalize_rating_drop_frequency(report_frequency: str) -> str:
    normalized = str(report_frequency or "").strip().casefold()
    aliases = {
        "week": "weekly",
        "weekly": "weekly",
        "month": "monthly",
        "monthly": "monthly",
    }
    frequency = aliases.get(normalized)
    if not frequency:
        raise ValueError("report_frequency must be either weekly or monthly.")
    return frequency


def rating_snapshot_cutoff(
    report_frequency: str,
    *,
    now: datetime | None = None,
) -> datetime:
    frequency = normalize_rating_drop_frequency(report_frequency)
    days = 7 if frequency == "weekly" else 30
    return (now or datetime.utcnow()) - timedelta(days=days)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _percent_drop(current_rating: float, previous_rating: float) -> float:
    if previous_rating == 0:
        return 0.0

    return round(((previous_rating - current_rating) / previous_rating) * 100, 1)


def build_rating_drop_report(
    *,
    current_snapshot: dict | None,
    previous_snapshot: dict | None,
    report_frequency: str,
    previous_cutoff: datetime,
) -> dict:
    frequency = normalize_rating_drop_frequency(report_frequency)
    current_rating = _as_float(
        current_snapshot.get("rating") if current_snapshot else None
    )
    previous_rating = _as_float(
        previous_snapshot.get("rating") if previous_snapshot else None
    )

    comparison_available = (
        current_rating is not None
        and previous_rating is not None
    )
    rating_drop = (
        current_rating < previous_rating
        if comparison_available
        else False
    )
    percentage_of_drops = (
        _percent_drop(current_rating, previous_rating)
        if rating_drop and previous_rating is not None
        else 0.0
        if comparison_available
        else None
    )

    return {
        "report_frequency": frequency,
        "current_ratings": current_rating,
        "previous_ratings": previous_rating,
        "rating_drop": rating_drop,
        "percentage_of_drops": percentage_of_drops,
        "comparison_available": comparison_available,
        "current_snapshot": {
            "recorded_at": current_snapshot.get("recorded_at")
            if current_snapshot
            else None,
            "user_ratings_total": _as_int(
                current_snapshot.get("user_ratings_total")
                if current_snapshot
                else None
            ),
        },
        "previous_snapshot": {
            "recorded_at": previous_snapshot.get("recorded_at")
            if previous_snapshot
            else None,
            "user_ratings_total": _as_int(
                previous_snapshot.get("user_ratings_total")
                if previous_snapshot
                else None
            ),
            "required_at_or_before": previous_cutoff.isoformat(),
        },
        "data_source": "google_place_rating_snapshots",
    }
