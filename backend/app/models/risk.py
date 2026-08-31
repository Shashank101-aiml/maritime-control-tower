from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.database.base import Base


class Risk(Base):
    __tablename__ = "risks"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    risk_type = Column(String(50), nullable=False, default="operational")
    category = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    likelihood = Column(String(30), nullable=False, default="medium")
    impact = Column(String(30), nullable=False, default="medium")
    estimated_cost = Column(Float, nullable=True)
    mitigation_plan = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="open")
    is_active = Column(Boolean, nullable=False, default=True)