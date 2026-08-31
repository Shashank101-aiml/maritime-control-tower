from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.risk import Risk
from app.schemas.risk import RiskCreate, RiskUpdate


def get_risk(db: Session, risk_id: int) -> Optional[Risk]:
    return db.query(Risk).filter(Risk.id == risk_id).first()


def get_risks(db: Session, skip: int = 0, limit: int = 100) -> List[Risk]:
    return db.query(Risk).offset(skip).limit(limit).all()


def create_risk(db: Session, risk_in: RiskCreate) -> Risk:
    risk = Risk(**risk_in.dict())
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return risk


def update_risk(db: Session, db_risk: Risk, risk_in: RiskUpdate) -> Risk:
    update_data = risk_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_risk, field, value)
    db.add(db_risk)
    db.commit()
    db.refresh(db_risk)
    return db_risk


def delete_risk(db: Session, db_risk: Risk) -> Risk:
    db.delete(db_risk)
    db.commit()
    return db_risk