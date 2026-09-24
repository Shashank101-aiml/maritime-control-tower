from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class DelayAssessmentRequest(BaseModel):
    """A lane between two real ports, and optionally when the cargo loads."""

    origin: str = Field(min_length=1, max_length=80)
    destination: str = Field(min_length=1, max_length=80)
    loading_date: Optional[date] = None


class VoyagePlanUpdate(BaseModel):
    """What the operator expects of a vessel's current voyage. Either field
    may be left empty to fall back on what the ship broadcasts."""

    destination_port: Optional[str] = Field(default=None, max_length=80)
    scheduled_arrival: Optional[datetime] = None
