"""The logistics graph: ports as nodes, shipping lanes as edges.

This is the keystone the spec's Simulation Agent (Slice 08) and
Optimization Agent (Slice 06) build on -- neither "what if this lane
becomes unavailable" nor "find the best route by cost/delay/risk" means
anything without a graph to modify or search.

What's real data vs. what's estimated, explicitly:
  - Node country/region/congestion metrics: real, from
    data/cleaned/port_congestion.csv (latest week per port).
  - Node/waypoint coordinates: curated reference data (see
    coordinates.py), not derived from any pipeline.
  - Edge distance_nm: real geometry -- great-circle segments summed
    through the real waypoint coordinates a lane actually passes
    through, not a single point-to-point line over land.
  - Edge transit_days: distance_nm / an assumed service speed (labeled
    below), not observed transit data.
  - Edge risk: real and live -- the live sea-state score for whichever
    monitored corridors the lane crosses (RiskAgent, same model backing
    /api/risks/corridors), combined with each endpoint port's real
    congestion_index percentile within its own historical distribution.
  - Edge cost_usd / emissions_estimate: NOT real. Distance-proportional
    placeholders, tagged with cost_model/emissions_model so nothing
    downstream can mistake them for sourced freight or bunker data.
    Slice 06 owns replacing these with something defensible.
"""

import csv
from collections import defaultdict
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from app.agents.ingestion.live_conditions_client import MONITORED_LOCATIONS
from app.twin.coordinates import PORT_COORDINATES
from app.twin.lanes import SHIPPING_LANES

PORT_CONGESTION_CSV = (
    Path(__file__).resolve().parents[3] / "data" / "cleaned" / "port_congestion.csv"
)

WAYPOINT_COORDINATES: Dict[str, tuple] = {
    loc["name"]: (loc["lat"], loc["lon"]) for loc in MONITORED_LOCATIONS
}

EARTH_RADIUS_NM = 3440.065  # nautical miles

# Typical container-vessel service speed. A labeled assumption, not
# observed data -- actual speeds vary by service and by fuel-saving
# "slow steaming" practice (commonly 14-18 knots since ~2010).
SERVICE_SPEED_KNOTS = 18.0

# Distance-proportional placeholders -- see module docstring. Neither
# figure is sourced from real freight-rate or bunker-fuel data; the
# _model fields on every edge exist so that's never ambiguous to a
# caller.
COST_PER_NM_USD = 1.0
EMISSIONS_PER_NM = 1.0


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in nautical miles."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_NM * asin(sqrt(a))


def _route_distance_nm(port_a: str, port_b: str, waypoints: List[str]) -> float:
    """Sum of great-circle segments through each named waypoint, in
    order. A lane with no waypoints is a single port-to-port segment --
    fine for routes that don't cross a monitored strait/canal/cape, but
    still a straight line rather than a real sailed track."""
    points = [PORT_COORDINATES[port_a]]
    for name in waypoints:
        points.append(WAYPOINT_COORDINATES[name])
    points.append(PORT_COORDINATES[port_b])

    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:]):
        total += haversine_nm(lat1, lon1, lat2, lon2)
    return total


class DigitalTwin:
    def __init__(self) -> None:
        self.graph = nx.MultiGraph()
        self._build_nodes()
        self._build_edges()

    # -- Nodes --------------------------------------------------------

    def _load_latest_port_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Most recent week_start row per port, plus the full historical
        congestion_index series per port (needed for the percentile
        ranking used in risk scoring)."""
        latest: Dict[str, Dict[str, Any]] = {}
        history: Dict[str, List[float]] = defaultdict(list)

        with open(PORT_CONGESTION_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                port = row["port"]
                history[port].append(float(row["congestion_index"]))
                if port not in latest or row["week_start"] > latest[port]["week_start"]:
                    latest[port] = row

        self._congestion_history = history
        return latest

    def _congestion_percentile(self, port: str, value: Optional[float]) -> int:
        """Where this port's latest congestion_index falls within its
        own historical distribution -- a data-derived 0-100 scale
        rather than an assumed threshold, since the raw index (observed
        range ~0.6-8.0 in this dataset) has no natural 0-100 meaning on
        its own."""
        series = self._congestion_history.get(port)
        if not series or value is None:
            return 0
        return round(100 * sum(1 for v in series if v <= value) / len(series))

    def _build_nodes(self) -> None:
        metrics = self._load_latest_port_metrics()
        for port, (lat, lon) in PORT_COORDINATES.items():
            row = metrics.get(port, {})
            congestion_index = float(row["congestion_index"]) if row else None
            self.graph.add_node(
                port,
                lat=lat,
                lon=lon,
                country=row.get("country"),
                region=row.get("region"),
                congestion_index=congestion_index,
                congestion_percentile=self._congestion_percentile(port, congestion_index),
                avg_wait_days=float(row["avg_wait_days"]) if row else None,
                berth_delay_hrs=float(row["berth_delay_hrs"]) if row else None,
                port_utilization_pct=float(row["port_utilization_pct"]) if row else None,
                metrics_as_of=row.get("week_start"),
            )

    # -- Edges ----------------------------------------------------------

    def _build_edges(self) -> None:
        for lane in SHIPPING_LANES:
            distance_nm = _route_distance_nm(lane.port_a, lane.port_b, lane.waypoints)
            transit_days = distance_nm / (SERVICE_SPEED_KNOTS * 24)
            self.graph.add_edge(
                lane.port_a,
                lane.port_b,
                key=lane.lane_id,
                lane_id=lane.lane_id,
                waypoints=list(lane.waypoints),
                distance_nm=round(distance_nm),
                transit_days=round(transit_days, 1),
                cost_usd=round(distance_nm * COST_PER_NM_USD),
                cost_model="distance_based_placeholder",
                emissions_estimate=round(distance_nm * EMISSIONS_PER_NM),
                emissions_model="distance_based_placeholder",
                # Populated by annotate_risk() -- None until then, rather
                # than a fabricated default, since "no risk score yet" and
                # "confirmed zero risk" are not the same claim.
                risk=None,
                risk_reason=None,
            )

    def annotate_risk(self, corridor_scores: Dict[str, int]) -> None:
        """Sets each edge's live risk score: the worst of (a) the live
        risk score for any monitored corridor the lane crosses, and (b)
        either endpoint port's own congestion percentile. Takes the
        worse of the two rather than averaging them, since a single
        severe factor -- a storm on an otherwise uncongested lane, or a
        badly congested port pair in calm seas -- should not be diluted
        by an unrelated calm one.

        corridor_scores: {corridor_name: 0-100 risk score}, e.g. from
        RiskAgent applied to each of LiveConditionsClient().get_all_events()
        (the same computation /api/risks/corridors already does).
        """
        for port_a, port_b, lane_id, data in self.graph.edges(keys=True, data=True):
            waypoint_scores = [
                corridor_scores[name] for name in data["waypoints"] if name in corridor_scores
            ]
            corridor_component = max(waypoint_scores) if waypoint_scores else 0

            a_pct = self.graph.nodes[port_a].get("congestion_percentile") or 0
            b_pct = self.graph.nodes[port_b].get("congestion_percentile") or 0
            congestion_component = max(a_pct, b_pct)

            if corridor_component >= congestion_component:
                risk, reason = corridor_component, (
                    f"Live sea-state risk on this lane's corridor(s): {corridor_component}/100."
                    if waypoint_scores else "No monitored corridor on this lane; risk is congestion-only."
                )
            else:
                worse_port = port_a if a_pct >= b_pct else port_b
                risk, reason = congestion_component, (
                    f"{worse_port}'s congestion is at the {congestion_component}th percentile "
                    "of its own history."
                )

            self.graph.edges[port_a, port_b, lane_id]["risk"] = risk
            self.graph.edges[port_a, port_b, lane_id]["risk_reason"] = reason

    # -- Serialization --------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        nodes = [
            {"id": port, **attrs} for port, attrs in self.graph.nodes(data=True)
        ]
        edges = [
            {"port_a": a, "port_b": b, **attrs}
            for a, b, attrs in self.graph.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}


_shared_twin: Optional[DigitalTwin] = None


def get_digital_twin() -> DigitalTwin:
    """Module-level singleton -- the graph topology (nodes, distances,
    lanes) is static, so it's built once per process. Live risk is
    re-annotated on every read via annotate_risk(), not baked in here."""
    global _shared_twin
    if _shared_twin is None:
        _shared_twin = DigitalTwin()
    return _shared_twin
