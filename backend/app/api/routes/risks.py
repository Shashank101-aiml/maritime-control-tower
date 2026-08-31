from fastapi import APIRouter

from app.agents.ingestion.ingestion_agent import IngestionAgent
from app.agents.risk.risk_agent import RiskAgent

router = APIRouter()

@router.get("/risks")
def get_risk():

    event = IngestionAgent().collect_data()

    risk_data = RiskAgent().calculate_risk(event)

    return {
        "risk_score": risk_data.get("score", 0),
        "details": risk_data
    }