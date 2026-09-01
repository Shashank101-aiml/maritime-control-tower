"""Live vessel positions from AISStream.io.

AISStream pushes AIS messages over a WebSocket rather than exposing a
request/response API, so this runs a persistent background connection in
a daemon thread and keeps an in-memory registry of the most recent
position per vessel. HTTP routes then read that registry instantly
instead of opening a socket per request.

Requires a free API key from https://aisstream.io (set AISSTREAM_API_KEY).
Without one the collector stays dormant and the registry reports
`configured: False` -- the UI says no feed is connected rather than
showing invented vessels.

Subscription and message shapes follow the AISStream v0 protocol:
    -> {"APIKey": ..., "BoundingBoxes": [[[lat,lon],[lat,lon]]],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"]}
    <- {"MessageType": ..., "MetaData": {...}, "Message": {...}}
"""

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.ingestion.live_conditions_client import MONITORED_LOCATIONS
from app.core.logging import get_logger

logger = get_logger(__name__)

AIS_STREAM_URL = "wss://stream.aisstream.io/v0/stream"

# Half-size of the box drawn around each monitored corridor, in degrees
# (~1.5 deg is roughly 165 km at the equator).
CORRIDOR_BOX_HALF_DEGREES = 1.5

# A vessel not heard from for this long is dropped from the registry --
# AIS reception is patchy, and a stale position presented as current
# would be misleading.
VESSEL_TTL_SECONDS = 1800

RECONNECT_BASE_DELAY = 5
RECONNECT_MAX_DELAY = 300

# AIS numeric ship-type codes -> human labels, per ITU-R M.1371.
# Specific codes are checked before ranges so e.g. 52 (tug) is not
# swallowed by the 50-59 "special craft" band.
_SHIP_TYPE_EXACT = {
    0: "Unknown",
    29: "SAR aircraft",
    30: "Fishing",
    31: "Tug / Towing",
    32: "Tug / Towing",
    33: "Dredging / Underwater ops",
    34: "Diving ops",
    35: "Military",
    36: "Sailing",
    37: "Pleasure craft",
    50: "Pilot vessel",
    51: "Search & rescue",
    52: "Tug / Towing",
    53: "Port tender",
    54: "Anti-pollution",
    55: "Law enforcement",
    58: "Medical transport",
}


def _ship_type_label(code: Optional[int]) -> str:
    if code is None:
        return "Unknown"
    if code in _SHIP_TYPE_EXACT:
        return _SHIP_TYPE_EXACT[code]
    if 20 <= code <= 28:
        return "Wing-in-ground"
    if 40 <= code <= 49:
        return "High-speed craft"
    if 60 <= code <= 69:
        return "Passenger"
    if 70 <= code <= 79:
        return "Cargo"
    if 80 <= code <= 89:
        return "Tanker"
    if 90 <= code <= 99:
        return "Other"
    return "Unknown"


NAV_STATUS = {
    0: "Under way using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Under way sailing",
}


def corridor_bounding_boxes() -> List[List[List[float]]]:
    """One box per monitored corridor, in AISStream's
    [[lat_min, lon_min], [lat_max, lon_max]] form."""
    boxes = []
    for loc in MONITORED_LOCATIONS:
        lat, lon = loc["lat"], loc["lon"]
        boxes.append([
            [lat - CORRIDOR_BOX_HALF_DEGREES, lon - CORRIDOR_BOX_HALF_DEGREES],
            [lat + CORRIDOR_BOX_HALF_DEGREES, lon + CORRIDOR_BOX_HALF_DEGREES],
        ])
    return boxes


def vessels_in_box(lat: float, lon: float, vessels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Vessels from a list_vessels() snapshot whose last known position
    falls inside one corridor's box -- the same box AISStream was asked
    to subscribe to, so "in this corridor" means the same thing here as
    it did in the subscription."""
    lat_min, lat_max = lat - CORRIDOR_BOX_HALF_DEGREES, lat + CORRIDOR_BOX_HALF_DEGREES
    lon_min, lon_max = lon - CORRIDOR_BOX_HALF_DEGREES, lon + CORRIDOR_BOX_HALF_DEGREES
    matched = []
    for vessel in vessels:
        vlat, vlon = vessel.get("latitude"), vessel.get("longitude")
        if vlat is None or vlon is None:
            continue
        if lat_min <= vlat <= lat_max and lon_min <= vlon <= lon_max:
            matched.append(vessel)
    return matched


class VesselRegistry:
    """Thread-safe store of the latest known position per MMSI."""

    def __init__(self, ttl_seconds: int = VESSEL_TTL_SECONDS) -> None:
        self._vessels: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self.connected = False
        self.last_message_at: Optional[float] = None
        self.last_error: Optional[str] = None

    def upsert(self, mmsi: int, data: Dict[str, Any]) -> None:
        with self._lock:
            existing = self._vessels.get(mmsi, {})
            existing.update({k: v for k, v in data.items() if v is not None})
            existing["mmsi"] = mmsi
            existing["_seen_at"] = time.monotonic()
            self._vessels[mmsi] = existing
        self.last_message_at = time.time()

    def list_vessels(self) -> List[Dict[str, Any]]:
        """Non-stale vessels, most recently heard first."""
        cutoff = time.monotonic() - self._ttl
        with self._lock:
            fresh = [v for v in self._vessels.values() if v.get("_seen_at", 0) >= cutoff]
            # drop expired entries so the dict doesn't grow without bound
            self._vessels = {v["mmsi"]: v for v in fresh}
        fresh.sort(key=lambda v: v.get("_seen_at", 0), reverse=True)
        return [{k: v for k, v in vessel.items() if not k.startswith("_")} for vessel in fresh]

    def count(self) -> int:
        return len(self.list_vessels())


# Process-wide registry shared by the collector thread and the API routes.
registry = VesselRegistry()


class AISStreamCollector:
    """Background AISStream subscriber. Start once at application startup."""

    def __init__(self, api_key: Optional[str], vessel_registry: VesselRegistry = registry) -> None:
        self.api_key = api_key
        self.registry = vessel_registry
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def start(self) -> bool:
        """Launch the collector. Returns False if no API key is set."""
        if not self.configured:
            logger.info("AISSTREAM_API_KEY not set - live vessel tracking disabled.")
            return False
        if self._thread and self._thread.is_alive():
            return True

        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="aisstream", daemon=True)
        self._thread.start()
        logger.info("AISStream collector started.")
        return True

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._consume_forever())
        finally:
            loop.close()

    async def _consume_forever(self) -> None:
        import asyncio

        import websockets

        delay = RECONNECT_BASE_DELAY
        subscription = json.dumps({
            "APIKey": self.api_key,
            "BoundingBoxes": corridor_bounding_boxes(),
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        })

        while not self._stop.is_set():
            try:
                async with websockets.connect(AIS_STREAM_URL, open_timeout=20) as ws:
                    await ws.send(subscription)
                    self.registry.connected = True
                    self.registry.last_error = None
                    delay = RECONNECT_BASE_DELAY  # reset backoff on success
                    logger.info("AISStream connected; subscribed to %d corridor boxes.",
                                len(corridor_bounding_boxes()))

                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        try:
                            self._handle_message(json.loads(raw))
                        except Exception as exc:
                            logger.debug("Skipping malformed AIS message: %s", exc)

            except Exception as exc:
                self.registry.connected = False
                self.registry.last_error = str(exc)
                logger.warning("AISStream disconnected (%s); retrying in %ss", exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX_DELAY)  # exponential backoff

        self.registry.connected = False

    def _handle_message(self, payload: Dict[str, Any]) -> None:
        message_type = payload.get("MessageType")
        metadata = payload.get("MetaData") or {}
        body = (payload.get("Message") or {}).get(message_type) or {}

        mmsi = metadata.get("MMSI") or body.get("UserID")
        if not mmsi:
            return

        name = (metadata.get("ShipName") or body.get("Name") or "").strip() or None

        if message_type == "PositionReport":
            self.registry.upsert(int(mmsi), {
                "name": name,
                "latitude": body.get("Latitude", metadata.get("latitude")),
                "longitude": body.get("Longitude", metadata.get("longitude")),
                "sog_knots": body.get("Sog"),
                "cog_degrees": body.get("Cog"),
                "heading_degrees": _valid_heading(body.get("TrueHeading")),
                "nav_status": NAV_STATUS.get(body.get("NavigationalStatus")),
                "last_report_utc": metadata.get("time_utc")
                or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

        elif message_type == "ShipStaticData":
            dimension = body.get("Dimension") or {}
            self.registry.upsert(int(mmsi), {
                "name": name,
                "imo": body.get("ImoNumber"),
                "call_sign": (body.get("CallSign") or "").strip() or None,
                "ship_type": _ship_type_label(body.get("Type")),
                "destination": (body.get("Destination") or "").strip() or None,
                "draught_m": body.get("MaximumStaticDraught"),
                "length_m": _dimension_sum(dimension.get("A"), dimension.get("B")),
                "width_m": _dimension_sum(dimension.get("C"), dimension.get("D")),
            })


def _valid_heading(value: Any) -> Optional[int]:
    """AIS uses 511 to mean 'heading not available'."""
    try:
        heading = int(value)
    except (TypeError, ValueError):
        return None
    return heading if 0 <= heading <= 359 else None


def _dimension_sum(a: Any, b: Any) -> Optional[int]:
    try:
        return int(a) + int(b)
    except (TypeError, ValueError):
        return None
