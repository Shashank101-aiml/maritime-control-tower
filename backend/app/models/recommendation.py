from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database.base import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    recommendation_type = Column(String(50), nullable=False, default="operation")
    summary = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    priority = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="pending")
    source = Column(String(100), nullable=True)
    is_implemented = Column(Boolean, nullable=False, default=False)