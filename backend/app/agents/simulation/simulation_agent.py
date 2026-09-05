"""Real what-if scenarios over the digital twin (spec Slice 08 / section
11): what would RouteOptimizer recommend if a chosen monitored corridor's
conditions worsen, or the corridor became fully impassable -- compared
against today's real baseline recommendation for the same origin/
destination.

Every scenario runs on a *copy* of the live digital twin's graph; the
shared singleton other requests read (GET /api/twin, RouteAgent,
the coordinator) is never mutated. Real distance/cost/congestion for
every lane not crossing the chosen corridor is untouched -- only the
chosen corridor's crossing lanes are modified, and the modification
itself is a real graph operation (raise risk to a labeled severity
band, or remove the edges outright), not an invented output route.
"""

from typing import Dict, Optional

import networkx as nx

from app.agents.ingestion.live_conditions_client import MONITORED_LOCATIONS
from app.agents.route.optimizer import MAX_HOPS, RouteCandidate, RouteOptimizer
from app.core.config import settings
from app.schemas.agent_io import ScenarioResult
from app.twin.digital_twin import fetch_live_corridor_scores, get_digital_twin

MONITORED_LOCATION_NAMES = {loc["name"] for loc in MONITORED_LOCATIONS}

SCENARIOS = ("NONE", "MODERATE", "SEVERE")

# A labeled simulated input, not a measured one -- matches the
# "elevated risk" band (>=60) already used for badges/coloring across
# the frontend (RouteComparisonChart, RiskAnalysis, Route Planning's
# lane picker), so a moderate scenario reads as "elevated", not
# arbitrary.
MODERATE_DISRUPTION_RISK = 70


class SimulationAgent:
    def __init__(self, optimizer: Optional[RouteOptimizer] = None) -> None:
        self.optimizer = optimizer or RouteOptimizer()

    def simulate(
        self,
        origin: str,
        destination: str,
        corridor: str,
        scenario: str,
        weights: Optional[Dict[str, float]] = None,
    ) -> ScenarioResult:
        scenario = scenario.upper()
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario {scenario!r}; must be one of {SCENARIOS}.")
        if corridor not in MONITORED_LOCATION_NAMES:
            raise ValueError(f"{corridor!r} is not a monitored corridor.")

        weights = weights or settings.ROUTE_OPTIMIZATION_WEIGHTS

        live_twin = get_digital_twin()
        live_twin.annotate_risk(fetch_live_corridor_scores())
        # Raises ValueError (propagated) if either port is unknown or
        # unreachable -- same as RouteAgent, no honest fallback to invent.
        baseline = self.optimizer.find_routes(live_twin.graph, origin, destination, weights)[0]

        if scenario == "NONE":
            return self._result(
                scenario, corridor, origin, destination, baseline,
                scenario_candidate=baseline, lanes_affected=0,
                summary=f"No disruption simulated -- this is today's real recommendation via {' + '.join(baseline.lane_ids)}.",
            )

        # Independent copy: NetworkX's Graph.copy() gives fresh node/edge
        # attribute dicts, so mutating this one never touches the shared
        # singleton every other live request reads.
        sim_graph = live_twin.graph.copy()

        # Scoped to lanes that actually appear on some candidate path
        # between this origin and destination -- not every lane anywhere
        # in the whole network that happens to cross the corridor, which
        # would count disruptions irrelevant to this specific query.
        candidate_paths = nx.all_simple_edge_paths(live_twin.graph, origin, destination, cutoff=MAX_HOPS)
        relevant_lane_ids = {key for path in candidate_paths for (_, _, key) in path}
        affected = [
            (u, v, k) for u, v, k, data in sim_graph.edges(keys=True, data=True)
            if k in relevant_lane_ids and corridor in (data.get("waypoints") or [])
        ]

        if not affected:
            return self._result(
                scenario, corridor, origin, destination, baseline,
                scenario_candidate=baseline, lanes_affected=0,
                summary=f"No lane crosses {corridor} directly -- a {scenario.lower()} disruption there doesn't change this route.",
            )

        if scenario == "MODERATE":
            for u, v, k in affected:
                sim_graph.edges[u, v, k]["risk"] = max(sim_graph.edges[u, v, k]["risk"], MODERATE_DISRUPTION_RISK)
                sim_graph.edges[u, v, k]["risk_reason"] = f"Simulated moderate disruption at {corridor}."
        else:  # SEVERE
            sim_graph.remove_edges_from(affected)

        try:
            scenario_best = self.optimizer.find_routes(sim_graph, origin, destination, weights)[0]
        except ValueError:
            return self._result(
                scenario, corridor, origin, destination, baseline,
                scenario_candidate=None, lanes_affected=len(affected),
                summary=(
                    f"No route survives a {scenario.lower()} disruption at {corridor} -- "
                    f"{origin} and {destination} would be disconnected within the optimizer's hop limit."
                ),
            )

        route_changed = scenario_best.lane_ids != baseline.lane_ids
        if route_changed:
            summary = (
                f"A {scenario.lower()} disruption at {corridor} would reroute this journey from "
                f"{' + '.join(baseline.lane_ids)} (risk {baseline.risk}/100) to "
                f"{' + '.join(scenario_best.lane_ids)} (risk {scenario_best.risk}/100)."
            )
        else:
            unchanged_risk = scenario_best.risk == baseline.risk
            summary = (
                f"Even with a {scenario.lower()} disruption at {corridor}, "
                f"{' + '.join(baseline.lane_ids)} is still the best option -- "
                + (
                    f"its risk was already {baseline.risk}/100 from port congestion alone, "
                    "so this disruption doesn't change it."
                    if unchanged_risk else
                    f"risk rises from {baseline.risk} to {scenario_best.risk}/100, but no alternative scores better."
                )
            )

        return self._result(
            scenario, corridor, origin, destination, baseline,
            scenario_candidate=scenario_best, lanes_affected=len(affected),
            summary=summary,
        )

    def _result(
        self, scenario, corridor, origin, destination, baseline: RouteCandidate,
        scenario_candidate: Optional[RouteCandidate], lanes_affected: int, summary: str,
    ) -> ScenarioResult:
        return ScenarioResult(
            scenario=scenario,
            corridor=corridor,
            origin=origin,
            destination=destination,
            baseline_lane_ids=baseline.lane_ids,
            baseline_risk=baseline.risk,
            baseline_distance_nm=baseline.distance_nm,
            scenario_lane_ids=scenario_candidate.lane_ids if scenario_candidate else None,
            scenario_risk=scenario_candidate.risk if scenario_candidate else None,
            scenario_distance_nm=scenario_candidate.distance_nm if scenario_candidate else None,
            lanes_affected=lanes_affected,
            route_changed=bool(scenario_candidate) and scenario_candidate.lane_ids != baseline.lane_ids,
            no_viable_route=scenario_candidate is None,
            summary=summary,
        )
