from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ActionableRecommendationStatusUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "title": "Staff_training",
                "status": "read",
            }
        },
    )

    user_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    status: Literal["read", "unread"] = "read"
