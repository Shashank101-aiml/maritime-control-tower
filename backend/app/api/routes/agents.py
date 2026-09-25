from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.models.governance import AgentExecutionTrace, AgentHealth, AgentIdentity

router = APIRouter()

# What each governed agent does, for the dashboard. Status and activity below
# come from the governance registry, not from this table.
ROLES = {
    "coordinator-agent": "Master workflow orchestrator",
    "ingestion-agent": "Telemetry & weather stream collector",
    "risk-agent": "Navigational hazard evaluator",
    "route-agent": "Multi-objective route optimizer",
    "decision-agent": "Route recommendation & trade-off decisions",
    "explanation-agent": "Decision transparency & explanation",
    "congestion-agent": "Port congestion predictor",
    "delay-agent": "Shipment delay & live voyage ETA",
    "fuel-agent": "Fuel burn, cost & CO2 estimator",
    "fleet-monitor-agent": "Operator fleet monitoring",
}

# A registry status that stops an agent running outranks its health reading.
NOT_RUNNING = {"QUARANTINED", "PAUSED", "DISABLED"}
HEALTH_TO_STATUS = {"HEALTHY": "ONLINE", "DEGRADED": "DEGRADED", "UNAVAILABLE": "OFFLINE"}


@router.get("/agents")
def get_agents(db: Session = Depends(get_db)):
    """Every agent registered with governance, with its real status and when
    it last executed (None if it never has)."""
    health = {h.agent_id: h for h in db.query(AgentHealth).all()}
    last_run = dict(
        db.query(AgentExecutionTrace.agent_id, func.max(AgentExecutionTrace.started_at))
        .group_by(AgentExecutionTrace.agent_id)
        .all()
    )
    agents = []
    for identity in db.query(AgentIdentity).order_by(AgentIdentity.agent_name).all():
        if identity.status in NOT_RUNNING:
            status = identity.status
        else:
            h = health.get(identity.id)
            status = HEALTH_TO_STATUS.get(h.status if h else "HEALTHY", "ONLINE")
        ran = last_run.get(identity.id)
        agents.append({
            "id": identity.id,
            "agent_name": identity.agent_name,
            "role": identity.description or ROLES.get(identity.id) or identity.agent_type.title(),
            "status": status,
            "version": identity.version,
            "executions": health[identity.id].execution_count if identity.id in health else 0,
            "last_active": ran.strftime("%Y-%m-%d %H:%M:%S UTC") if isinstance(ran, datetime) else None,
        })
    return agents
