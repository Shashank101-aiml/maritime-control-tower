"""Real multi-objective route optimization over the digital twin.

Replaces a fabricated version of this file that scored routes on
waypoint counts (`score = 50.0`, `+10` if origin/destination were
present, ...) and returned a hardcoded ETA string
(`f"2026-07-0{...}"`) regardless of any real distance or condition.
This one finds actual paths through app/twin/digital_twin.py's
NetworkX graph and scores them on real distance, transit time, cost,
emissions, and live risk.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import networkx as nx

DEFAULT_WEIGHTS: Dict[str, float] = {
    "risk": 0.4,
    "cost": 0.25,
    "delay": 0.25,
    "emissions": 0.1,
}

# Bounds path enumeration on a graph small enough (20 nodes, ~35 edges)
# that this rarely matters -- the twin's lanes were curated as real
# trade routes, so genuine port pairs are mostly 1-2 hops. A cutoff of
# 3 still allows real intra-regional connectors (e.g. Dubai -> Singapore
# -> Hong Kong) without letting path count explode.
MAX_HOPS = 3


@dataclass
class RouteCandidate:
    """One real path through the twin: an ordered sequence of real
    lane_ids with attributes summed/aggregated across every hop, not a
    label. `risk` is the worst single hop, not an average -- consistent
    with DigitalTwin.annotate_risk()'s own worst-of philosophy, since a
    route is only as safe as its riskiest leg. `score` is set by
    RouteOptimizer._rank() and is a weighted composite normalized
    against the other candidates in the same query -- only meaningful
    relative to them, not as an absolute figure."""

    lane_ids: List[str]
    origin: str
    destination: str
    distance_nm: float
    transit_days: float
    cost_usd: float
    emissions_estimate: float
    risk: int
    score: float = 0.0


class RouteOptimizer:
    def find_routes(
        self,
        graph: nx.MultiGraph,
        origin: str,
        destination: str,
        weights: Optional[Dict[str, float]] = None,
    ) -> List[RouteCandidate]:
        """Every real simple path (no repeated nodes) from origin to
        destination up to MAX_HOPS, scored and sorted ascending by
        composite score (index 0 = best/recommended).

        Raises ValueError if either port isn't in the twin, or if no
        path exists within MAX_HOPS -- there is no honest fallback
        route to invent in that case. Every edge's `risk` must already
        be set (see DigitalTwin.annotate_risk()) -- an unannotated
        graph fails loudly here (TypeError comparing None) rather than
        silently scoring on a fabricated zero risk.
        """
        if origin not in graph:
            raise ValueError(f"{origin!r} is not a port in the digital twin.")
        if destination not in graph:
            raise ValueError(f"{destination!r} is not a port in the digital twin.")

        edge_paths = list(
            nx.all_simple_edge_paths(graph, origin, destination, cutoff=MAX_HOPS)
        )
        if not edge_paths:
            raise ValueError(
                f"No route from {origin!r} to {destination!r} within {MAX_HOPS} hops."
            )

        candidates = [
            self._aggregate(graph, origin, destination, edge_path)
            for edge_path in edge_paths
        ]
        return self._rank(candidates, weights or DEFAULT_WEIGHTS)

    def _aggregate(
        self,
        graph: nx.MultiGraph,
        origin: str,
        destination: str,
        edge_path,
    ) -> RouteCandidate:
        """edge_path is a list of (u, v, key) triples from
        all_simple_edge_paths on a MultiGraph -- each triple already
        names the exact parallel edge (lane) taken at that hop, so this
        is a direct attribute lookup per hop, not a min-over-parallel-
        edges guess (the gotcha with NetworkX's default MultiGraph
        weight handling)."""
        lane_ids: List[str] = []
        distance_nm = transit_days = cost_usd = emissions_estimate = 0.0
        risks: List[int] = []

        for u, v, key in edge_path:
            attrs = graph.edges[u, v, key]
            lane_ids.append(key)
            distance_nm += attrs["distance_nm"]
            transit_days += attrs["transit_days"]
            cost_usd += attrs["cost_usd"]
            emissions_estimate += attrs["emissions_estimate"]
            risks.append(attrs["risk"])

        return RouteCandidate(
            lane_ids=lane_ids,
            origin=origin,
            destination=destination,
            distance_nm=round(distance_nm),
            transit_days=round(transit_days, 1),
            cost_usd=round(cost_usd),
            emissions_estimate=round(emissions_estimate),
            risk=max(risks),
        )

    def _rank(
        self, candidates: List[RouteCandidate], weights: Dict[str, float]
    ) -> List[RouteCandidate]:
        """Composite score = weighted sum of each metric, min-max
        normalized to 0-1 *within this candidate set* -- not against an
        invented absolute scale, since cost_usd/emissions_estimate are
        distance-based placeholders with no real absolute unit yet (see
        digital_twin.py's module docstring). Weights are normalized by
        their own sum, so a partial override (e.g. only bumping "risk")
        still produces a sensible ranking rather than requiring the
        caller to keep every weight in sync to 1.0."""
        total_weight = sum(weights.values()) or 1.0
        normalized_weights = {k: v / total_weight for k, v in weights.items()}

        def minmax(values: List[float]) -> List[float]:
            lo, hi = min(values), max(values)
            spread = hi - lo
            if spread == 0:
                return [0.0] * len(values)
            return [(v - lo) / spread for v in values]

        risk_n = minmax([c.risk for c in candidates])
        cost_n = minmax([c.cost_usd for c in candidates])
        delay_n = minmax([c.transit_days for c in candidates])
        emissions_n = minmax([c.emissions_estimate for c in candidates])

        for i, candidate in enumerate(candidates):
            candidate.score = round(
                normalized_weights.get("risk", 0.0) * risk_n[i]
                + normalized_weights.get("cost", 0.0) * cost_n[i]
                + normalized_weights.get("delay", 0.0) * delay_n[i]
                + normalized_weights.get("emissions", 0.0) * emissions_n[i],
                4,
            )

        return sorted(candidates, key=lambda c: c.score)
