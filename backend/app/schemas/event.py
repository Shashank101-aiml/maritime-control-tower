from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EventBase(BaseModel):
    event_type: str = Field(..., max_length=50)
    severity: str = Field("info", max_length=20)
    source: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    event_type: Optional[str] = Field(None, max_length=50)
    severity: Optional[str] = Field(None, max_length=20)
    source: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class Event(EventBase):
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True