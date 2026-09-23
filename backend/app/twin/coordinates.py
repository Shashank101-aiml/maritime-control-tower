"""Curated port coordinates for the digital twin.

data/cleaned/port_congestion.csv has real weekly congestion metrics for
these 20 ports (throughput, vessels at anchor, wait days, congestion
index, utilization, berth delay -- see DigitalTwin._load_port_metrics())
but no lat/lon column. This is the one piece of node data that isn't
already in the dataset: manually sourced port-area coordinates (public
port-authority / nautical-almanac locations), approximate at the scale
of the port itself rather than a specific berth or anchorage.

Everything else about a node -- country, region, congestion metrics --
comes from the CSV, not from here.

The Singapore coordinate matches MONITORED_LOCATIONS["Port of Singapore"]
in live_conditions_client.py deliberately, so the port node and the live
sea-state corridor of the same name refer to the same place.
"""

from typing import Dict, Tuple

PORT_COORDINATES: Dict[str, Tuple[float, float]] = {
    "Antwerp": (51.27, 4.34),
    "Busan": (35.10, 129.04),
    "Colombo": (6.95, 79.84),
    "Dubai (Jebel Ali)": (25.01, 55.06),
    "Felixstowe": (51.96, 1.35),
    "Guangzhou": (23.10, 113.30),
    "Hamburg": (53.55, 9.99),
    "Hong Kong": (22.30, 114.17),
    "Laem Chabang": (13.08, 100.88),
    "Long Beach": (33.75, -118.19),
    "Los Angeles": (33.73, -118.26),
    "New York": (40.67, -74.04),
    "Ningbo": (29.87, 121.55),
    "Qingdao": (36.07, 120.38),
    "Rotterdam": (51.95, 4.14),
    "Shanghai": (31.23, 121.47),
    "Shenzhen": (22.54, 114.05),
    "Singapore": (1.26, 103.84),
    "Tanjung Pelepas": (1.36, 103.55),
    "Tanjung Priok": (-6.10, 106.88),
}

# Real maritime chokepoints used purely for route *geometry* -- summing
# great-circle segments through a named waypoint like this is how
# digital_twin.py keeps a lane's plotted path from cutting across land,
# same idea as the 8 corridors in MONITORED_LOCATIONS. These aren't
# live sea-state monitored (no Open-Meteo feed keyed to them), so they
# carry no severity/live risk -- geometry only, kept separate from
# MONITORED_LOCATIONS so that distinction stays explicit rather than
# quietly implying a live reading exists where none does.
#
# Added because every Suez<->Atlantic lane (Europe or US East Coast)
# jumped straight from the Suez Canal waypoint to the destination port
# with nothing in between -- a straight line over that span cuts across
# Southern/Eastern Europe instead of following the real track out
# through the Strait of Gibraltar.
EXTRA_WAYPOINT_COORDINATES: Dict[str, Tuple[float, float]] = {
    "Strait of Gibraltar": (36.00, -5.60),
    # Offshore points that keep the Iberian / Biscay / West Africa legs
    # over water instead of cutting a corner across land.
    "Cape St. Vincent": (36.90, -10.00),
    "Cape Finisterre": (43.00, -10.50),
    "Ushant": (48.60, -5.80),
    "Off Cape Verde": (15.00, -25.00),
    "Southern North Sea": (52.60, 3.20),
    "German Bight": (54.00, 7.50),
}
