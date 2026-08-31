from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RecommendationBase(BaseModel):
    recommendation_type: str = Field("operation", max_length=50)
    summary: str = Field(..., max_length=255)
    details: Optional[str] = None
    priority: int = Field(0, ge=0)
    status: str = Field("pending", max_length=30)
    source: Optional[str] = Field(None, max_length=100)
    is_implemented: bool = Field(False)


class RecommendationCreate(RecommendationBase):
    pass


class RecommendationUpdate(BaseModel):
    recommendation_type: Optional[str] = Field(None, max_length=50)
    summary: Optional[str] = Field(None, max_length=255)
    details: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, max_length=30)
    source: Optional[str] = Field(None, max_length=100)
    is_implemented: Optional[bool] = None


class Recommendation(RecommendationBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True