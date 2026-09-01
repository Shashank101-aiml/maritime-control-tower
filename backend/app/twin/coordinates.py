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
