from fastapi import APIRouter

from app.agents.ingestion.ingestion_agent import IngestionAgent
from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/events")
def get_events():
    """The single most severe condition currently observed across the
    monitored corridors."""
    return IngestionAgent().collect_data()


@router.get("/conditions")
def get_conditions():
    """Live sea state for every monitored maritime corridor, worst first.

    Backed by Open-Meteo (no API key). Returns an explicit `source` of
    "live" or "unavailable" so the UI can say which it is showing rather
    than silently presenting stale or invented readings.
    """
    try:
        client = LiveConditionsClient()
        events = client.get_all_events()
        return {
            "source": "live",
            "provider": "open-meteo",
            "count": len(events),
            # Lets the UI show how fresh this is and when it next changes.
            **client.cache_status(),
            "conditions": events,
        }
    except Exception as exc:
        logger.warning("Live conditions sweep failed: %s", exc)
        return {
            "source": "unavailable",
            "provider": "open-meteo",
            "count": 0,
            "conditions": [],
            "error": str(exc),
        }
