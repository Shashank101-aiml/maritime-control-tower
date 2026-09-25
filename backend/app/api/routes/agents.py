from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.models.governance import AgentExecutionTrace, AgentHealth, AgentIdentity, AgentPermission

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

# A plain-language synopsis of each agent's objective, shown on hover.
SYNOPSES = {
    "coordinator-agent": "Runs the end-to-end workflow: collects live conditions, scores the risk, and for anything above nominal picks a route, decides and explains it. Every step is a governed call, and low-risk events skip the route and decision steps.",
    "ingestion-agent": "Gathers the live inputs the rest of the system reasons over: sea state for the 8 monitored corridors from Open-Meteo, plus AIS vessel positions. It lowers its confidence when it has to fall back to a weaker source.",
    "risk-agent": "Scores navigational hazard from 0 to 100 for a corridor from its wave, swell, wind and visibility readings, using a trained model with a rule-based fallback.",
    "route-agent": "Finds and ranks routes over the digital twin of ports and shipping lanes, weighing risk, cost, delay and emissions with weights that are configurable rather than hardcoded.",
    "decision-agent": "Turns the ranked routes into a recommendation: the expected delay, cost change and risk reduction against staying the course, and whether a human must approve it.",
    "explanation-agent": "Writes the plain-language reasons behind a decision, so an operator can see why a route was chosen. Template-based, with an optional language-model polish.",
    "congestion-agent": "Predicts whether a port is heading for congestion, using a model trained on weekly port throughput, waiting-time and berth-delay data.",
    "delay-agent": "Reports how long real container journeys on a lane take and how often they run late, and works out a live ETA for each of your ships from its AIS position and speed.",
    "fuel-agent": "Estimates fuel burned, cost and CO2 for a planned voyage, priced at live bunker prices, across ship classes and fuels from VLSFO to LNG and methanol.",
    "fleet-monitor-agent": "Watches the vessels operators register: follows each on live AIS, checks its position against the shipping lanes and sea state, and raises alerts when something needs attention.",
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
    permissions = {}
    for perm in db.query(AgentPermission).all():
        permissions.setdefault(perm.agent_id, []).append(f"{perm.action.lower()} {perm.resource.lower()}")
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
            "synopsis": SYNOPSES.get(identity.id) or identity.description,
            "confidence_threshold": identity.confidence_threshold,
            "risk_level": identity.risk_level,
            "permissions": sorted(permissions.get(identity.id, [])),
            "executions": health[identity.id].execution_count if identity.id in health else 0,
            "last_active": ran.strftime("%Y-%m-%d %H:%M:%S UTC") if isinstance(ran, datetime) else None,
        })
    return agents
