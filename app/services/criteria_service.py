#app.services.criteria_serivce.py
from collections import defaultdict
from typing import List, Dict


def aggregate_criteria_scores(reviews_analysis: List[dict]) -> Dict[str, float]:
    """
    Aggregate criteria scores for dashboard
    """
    bucket = defaultdict(list)

    for r in reviews_analysis:
        for criteria, score in r.get("criteria_scores", {}).items():
            bucket[criteria].append(score)

    return {
        criteria: round(sum(scores) / len(scores), 1)
        for criteria, scores in bucket.items()
    }


def normalize_criteria_scores(criteria_scores: dict):
    """
    Convert 1–5 scores to 0–100 for radar chart
    """
    return {
        category: round((score / 5) * 100, 1)
        for category, score in criteria_scores.items()
    }
