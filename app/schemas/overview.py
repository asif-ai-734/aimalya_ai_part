from pydantic import BaseModel, Field
from typing import Dict, List


class Strength(BaseModel):
    strength: str
    mentions: int


class Issue(BaseModel):
    issue: str
    mentions: int


class GrowthMetric(BaseModel):
    value: float | int
    display: str
    unit: str
    direction: str
    label: str
    percent_change: float | None = None
    percent_display: str | None = None


class OverviewResponse(BaseModel):
    overall_rating: float
    satisfaction_index: int
    review_volume: int
    response_rate: int
    growth: Dict[str, GrowthMetric] = Field(default_factory=dict)
    key_strengths: List[Strength]
    key_issues: List[Issue]
