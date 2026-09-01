from fastapi import APIRouter
from datetime import datetime
from app.agents.ingestion.ingestion_agent import IngestionAgent
from app.agents.risk.risk_agent import RiskAgent

router = APIRouter()

@router.get("/dashboard")
def get_dashboard_summary():
    event = IngestionAgent().collect_data()
    risk = RiskAgent().calculate_risk(event).model_dump()
    risk_score = risk.get("score", 0)
    return {
        "active_vessels": 42,
        "active_alerts": 3 if risk_score > 50 else 1,
        "average_fleet_risk": risk_score,
        "recent_events": [
            {
                "id": "EVT-1001",
                "event_type": event.get("event_type", "Storm"),
                "location": event.get("location", "Arabian Sea"),
                "severity": event.get("severity", "HIGH"),
                "timestamp": datetime.utcnow().strftime("%H:%M:%S UTC")
            },
            {
                "id": "EVT-1002",
                "event_type": "Piracy Warning",
                "location": "Gulf of Aden",
                "severity": "MEDIUM",
                "timestamp": "10 minutes ago"
            },
            {
                "id": "EVT-1003",
                "event_type": "Port Congestion",
                "location": "Singapore Port",
                "severity": "LOW",
                "timestamp": "1 hour ago"
            }
        ],
        "system_status": "OPERATIONAL"
    }
