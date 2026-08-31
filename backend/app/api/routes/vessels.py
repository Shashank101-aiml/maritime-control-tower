from fastapi import APIRouter

from app.agents.ingestion.ais_client import registry
from app.core.config import settings

router = APIRouter()


@router.get("/vessels")
def get_vessels(limit: int = 200):
    """Live vessel positions collected from AISStream.

    Always reports whether the feed is configured and connected, so the
    UI can distinguish "no key set", "connecting", and "connected but no
    vessels in range" instead of showing an ambiguous empty list.
    """
    configured = bool(settings.AISSTREAM_API_KEY)
    vessels = registry.list_vessels()[:limit] if configured else []

    if not configured:
        status = "not_configured"
    elif registry.connected:
        status = "connected"
    else:
        status = "connecting"

    return {
        "configured": configured,
        "status": status,
        "connected": registry.connected,
        "provider": "aisstream.io",
        "count": len(vessels),
        "last_message_at": registry.last_message_at,
        "error": registry.last_error,
        "vessels": vessels,
    }
