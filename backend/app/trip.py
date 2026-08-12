from pydantic import BaseModel, Field
from typing import List


class TripRequest(BaseModel):
    destination: str = Field(..., min_length=1)
    country: str = Field(default="")

    days: int = Field(..., ge=1)
    travelers: int = Field(..., ge=1)
    budget: float = Field(..., gt=0)

    travel_style: str = Field(default="balanced")
    interests: List[str] = Field(default_factory=list)