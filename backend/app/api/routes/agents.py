from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/agents")
def get_agents():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return [
        {
            "agent_name": "Coordinator Agent",
            "role": "Master Workflow Orchestrator",
            "status": "ONLINE",
            "last_active": now
        },
        {
            "agent_name": "Ingestion Agent",
            "role": "Telemetry & Weather Stream Collector",
            "status": "ONLINE",
            "last_active": now
        },
        {
            "agent_name": "Risk Assessment Agent",
            "role": "Navigational Hazard Evaluator",
            "status": "ONLINE",
            "last_active": now
        },
        {
            "agent_name": "Route Optimization Agent",
            "role": "Dynamic Waypoint & Corridor Planner",
            "status": "ONLINE",
            "last_active": now
        },
        {
            "agent_name": "Explanation Agent",
            "role": "Decision Transparency & NLP Synthesizer",
            "status": "ONLINE",
            "last_active": now
        }
    ]
