from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BusinessAccountStatusRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "business_name": "XYZ Food Corner",
                "action": "suspend",
            }
        },
    )

    business_name: str = Field(..., min_length=1)
    action: Literal["suspend", "unsuspend"]
