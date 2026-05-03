from pydantic import BaseModel, ConfigDict, Field


class GoalsSetupRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "business_name": "Abc coffe house",
                "competitors_urls": [
                    "map.google.com/CoffeeBean",
                    "maps.google.com/Starbucks",
                ],
                "report_frequency": "monthly",
                "goals": [
                    "improve_customer_satisfaction",
                    "improve_service_speed",
                    "increase_ratings",
                ],
            }
        },
    )

    business_name: str
    competitors_urls: list[str] = Field(..., min_length=1)
    report_frequency: str
    goals: list[str] = Field(..., min_length=1)
