from fastapi import APIRouter

from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.agents.risk.risk_agent import RiskAgent
from app.core.logging import get_logger
from app.twin.digital_twin import get_digital_twin

logger = get_logger(__name__)

router = APIRouter()


@router.get("/twin")
def get_twin_graph():
    """The logistics graph backing Simulation (Slice 08) and Optimization
    (Slice 06) -- 20 ports as nodes, real shipping lanes as edges, each
    edge's risk freshly computed from live sea-state plus real port
    congestion on every request. See app/twin/digital_twin.py's module
    docstring for exactly which fields are real data, which are labeled
    assumptions, and which are distance-based placeholders.
    """
    twin = get_digital_twin()

    try:
        events = LiveConditionsClient().get_all_events()
        agent = RiskAgent()
        corridor_scores = {
            event["location"]: agent.calculate_risk(event).score for event in events
        }
    except Exception as exc:
        logger.warning("Live conditions unavailable for twin risk annotation: %s", exc)
        corridor_scores = {}

    twin.annotate_risk(corridor_scores)

    return {
        **twin.to_dict(),
        "corridors_used": sorted(corridor_scores.keys()),
    }
