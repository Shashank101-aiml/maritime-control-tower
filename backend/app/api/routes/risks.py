from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.ingestion.ingestion_agent import IngestionAgent
from app.agents.risk.risk_agent import RiskAgent
from app.api.dependencies.database import get_db
from app.services.observation_service import record_risk, risk_history

router = APIRouter()


@router.get("/risks")
def get_risk(db: Session = Depends(get_db)):
    event = IngestionAgent().collect_data()
    risk_data = RiskAgent().calculate_risk(event)

    # Retained so the trajectory chart has real history to plot. Recording
    # never raises — a lost history row must not fail the request.
    record_risk(db, risk_data, location=event.get("location"))

    return {
        "risk_score": risk_data.get("score", 0),
        "details": risk_data,
    }


@router.get("/risks/history")
def get_risk_history(hours: int = 24, buckets: int = 24, db: Session = Depends(get_db)):
    """Recorded risk scores over time.

    Nothing is backfilled, so a freshly deployed instance legitimately
    returns mostly-empty buckets; `recorded_from` tells the UI how much
    history actually exists.
    """
    return risk_history(db, hours=hours, buckets=buckets)
