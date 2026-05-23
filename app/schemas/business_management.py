from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BusinessAccountStatusRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "business_name": "XYZ Food Corner",
                "action": "suspend",
            }
        },
    )

    user_id: str = Field(..., min_length=1)
    business_name: str = Field(..., min_length=1)
    action: Literal["suspend", "unsuspend"]
