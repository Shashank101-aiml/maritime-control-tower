"""Live AIS tracking of registered fleet vessels.

A second AISStream subscription, separate from the corridor feed: it asks
for the whole globe but filters to the MMSIs operators have registered, so
a ship is followed wherever it sails, not only inside the 8 monitored
corridors. AISStream accepts several concurrent connections on one key and
at most 50 MMSIs per subscription (see settings.FLEET_MAX_TRACKED_VESSELS).

Coverage is what terrestrial AIS receivers hear -- dense near coasts and
ports, patchy mid-ocean. A ship with no report yet is "awaiting signal",
never a guessed position.
"""

import threading
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, Iterable, List, Optional, Set

from app.agents.ingestion.ais_client import AISStreamCollector, VesselRegistry
from app.core.config import settings

GLOBAL_BOX = [[[-90.0, -180.0], [90.0, 180.0]]]
TRACKED_TTL_SECONDS = 24 * 3600


def _valid_position(lat: Any, lon: Any) -> bool:
    """AIS reports 91 / 181 for 'not available'."""
    try:
        return -90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0
    except (TypeError, ValueError):
        return False


class FleetTracker(AISStreamCollector):
    def __init__(self, api_key: Optional[str]) -> None:
        super().__init__(api_key, vessel_registry=VesselRegistry(ttl_seconds=TRACKED_TTL_SECONDS))
        self._mmsis: Set[int] = set()
        self._state_lock = threading.Lock()
        self._trails: Dict[int, Deque[List[Any]]] = {}
        self._received_at: Dict[int, datetime] = {}

    # -- what to watch ---------------------------------------------------

    def set_mmsis(self, mmsis: Iterable[int]) -> None:
        """Replace the watched set; reconnects with the new list if it changed."""
        wanted = {int(m) for m in mmsis}
        with self._state_lock:
            changed = wanted != self._mmsis
            self._mmsis = wanted
            for gone in [m for m in self._trails if m not in wanted]:
                self._trails.pop(gone, None)
                self._received_at.pop(gone, None)
        if changed:
            self._resubscribe.set()

    def watched(self) -> Set[int]:
        with self._state_lock:
            return set(self._mmsis)

    def _should_connect(self) -> bool:
        return bool(self._mmsis)

    def _subscription(self) -> Dict[str, Any]:
        return {
            "BoundingBoxes": GLOBAL_BOX,
            "FiltersShipMMSI": sorted(str(m) for m in self.watched()),
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }

    def _describe_subscription(self) -> str:
        return f"{len(self.watched())} fleet vessel(s)"

    # -- incoming messages -----------------------------------------------

    def _handle_message(self, payload: Dict[str, Any]) -> None:
        message_type = payload.get("MessageType")
        metadata = payload.get("MetaData") or {}
        body = (payload.get("Message") or {}).get(message_type) or {}
        raw_mmsi = metadata.get("MMSI") or body.get("UserID")
        try:
            mmsi = int(raw_mmsi)
        except (TypeError, ValueError):
            return
        if mmsi not in self.watched():
            return

        if message_type == "PositionReport":
            lat = body.get("Latitude", metadata.get("latitude"))
            lon = body.get("Longitude", metadata.get("longitude"))
            if not _valid_position(lat, lon):
                return
            super()._handle_message(payload)
            now = datetime.utcnow()
            with self._state_lock:
                self._received_at[mmsi] = now
                trail = self._trails.setdefault(mmsi, deque(maxlen=settings.FLEET_TRAIL_POINTS))
                # [lat, lon, time, speed over ground] -- speed lets a voyage ETA use
                # the ship's recent pace instead of one instantaneous reading.
                trail.append([float(lat), float(lon), now.isoformat() + "Z", body.get("Sog")])
        else:
            super()._handle_message(payload)

    # -- reading ---------------------------------------------------------

    def latest(self, mmsi: int) -> Optional[Dict[str, Any]]:
        """Most recent live record (position and any static data) for one
        watched vessel, with the wall-clock time the position was received."""
        record = self.registry.get(int(mmsi))
        if record is None:
            return None
        with self._state_lock:
            record["received_at"] = self._received_at.get(int(mmsi))
        return record

    def trail(self, mmsi: int) -> List[List[Any]]:
        with self._state_lock:
            return list(self._trails.get(int(mmsi), []))

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self.configured,
            "connected": bool(self.registry.connected),
            "tracked": len(self.watched()),
            "capacity": settings.FLEET_MAX_TRACKED_VESSELS,
            "last_error": self.registry.last_error,
        }


# Process-wide instance shared by the monitoring agent and the API routes.
fleet_tracker = FleetTracker(settings.AISSTREAM_API_KEY)
