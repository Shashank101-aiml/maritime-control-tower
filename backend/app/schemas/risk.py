from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RiskBase(BaseModel):
    risk_type: str = Field("operational", max_length=50)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    likelihood: str = Field("medium", max_length=30)
    impact: str = Field("medium", max_length=30)
    estimated_cost: Optional[float] = None
    mitigation_plan: Optional[str] = None
    status: str = Field("open", max_length=30)
    is_active: bool = Field(True)


class RiskCreate(RiskBase):
    pass


class RiskUpdate(BaseModel):
    risk_type: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    likelihood: Optional[str] = Field(None, max_length=30)
    impact: Optional[str] = Field(None, max_length=30)
    estimated_cost: Optional[float] = None
    mitigation_plan: Optional[str] = None
    status: Optional[str] = Field(None, max_length=30)
    is_active: Optional[bool] = None


class Risk(RiskBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
