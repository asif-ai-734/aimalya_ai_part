from pydantic import BaseModel, ConfigDict, Field


class BusinessLocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    google_maps_url: str
    address_or_city: str


class BusinessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
    locations: list[BusinessLocationInput] = Field(..., min_length=1)


class BusinessSetupRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "businesses": [
                    {
                        "name": "XYZ Food Corner",
                        "category": "restaurant",
                        "locations": [
                            {
                                "google_maps_url": "https://maps.google.com/...",
                                "address_or_city": "Uttara, Dhaka",
                            },
                            {
                                "google_maps_url": "https://maps.google.com/...",
                                "address_or_city": "Uttara, Dhaka",
                            },
                        ],
                    },
                    {
                        "name": "ABC Coffee Shop",
                        "category": "cafe",
                        "locations": [
                            {
                                "google_maps_url": "https://maps.google.com/...",
                                "address_or_city": "Uttara, Dhaka",
                            }
                        ],
                    },
                ]
            }
        },
    )

    businesses: list[BusinessInput] = Field(..., min_length=1)
