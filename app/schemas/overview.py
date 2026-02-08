from pydantic import BaseModel
from typing import List


class Strength(BaseModel):
    strength: str
    mentions: int


class Issue(BaseModel):
    issue: str
    mentions: int


class OverviewResponse(BaseModel):
    overall_rating: float
    satisfaction_index: int
    review_volume: int
    response_rate: int
    key_strengths: List[Strength]
    key_issues: List[Issue]
