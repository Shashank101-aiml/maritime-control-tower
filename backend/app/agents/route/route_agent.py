"""Real route recommendation, backed by RouteOptimizer over the digital
twin (app/twin/digital_twin.py). Replaces a fabricated four-band
if/elif ladder that returned one of four fixed route names --
"Cape of Good Hope Bypass", "Corridor Beta (Southern Bypass)", "Suez
Canal Commercial Passage", "Direct Deepwater Corridor" -- regardless of
any real distance, risk, or cost.
"""

from typing import Dict, Optional

from app.agents.route.optimizer import RouteCandidate, RouteOptimizer
from app.core.config import settings
from app.schemas.agent_io import RouteAlternative, RouteRecommendation
from app.twin.digital_twin import fetch_live_corridor_scores, get_digital_twin


class RouteAgent:
    def __init__(self, optimizer: Optional[RouteOptimizer] = None) -> None:
        self.optimizer = optimizer or RouteOptimizer()

    def suggest_route(
        self,
        origin: str,
        destination: str,
        weights: Optional[Dict[str, float]] = None,
    ) -> RouteRecommendation:
        """Ranks every real path from origin to destination through the
        digital twin (risk annotated from the live feed, same as
        GET /api/twin) and returns the best as the recommendation, the
        rest as alternatives. Raises ValueError (propagated from
        RouteOptimizer) if either port is unknown or unreachable within
        the hop limit -- there is no honest fallback route to invent.
        """
        twin = get_digital_twin()
        twin.annotate_risk(fetch_live_corridor_scores())

        candidates = self.optimizer.find_routes(
            twin.graph, origin, destination, weights or settings.ROUTE_OPTIMIZATION_WEIGHTS
        )
        best, rest = candidates[0], candidates[1:]

        return RouteRecommendation(
            route=f"{origin} to {destination} via {' + '.join(best.lane_ids)}",
            reason=self._describe(best),
            origin=origin,
            destination=destination,
            lane_ids=best.lane_ids,
            distance_nm=best.distance_nm,
            transit_days=best.transit_days,
            cost_usd=best.cost_usd,
            emissions_estimate=best.emissions_estimate,
            risk=best.risk,
            score=best.score,
            alternatives=[self._as_alternative(candidate) for candidate in rest],
        )

    def _describe(self, candidate: RouteCandidate) -> str:
        hops = f"{len(candidate.lane_ids)}-leg" if len(candidate.lane_ids) > 1 else "direct"
        return (
            f"{hops.capitalize()} route via {', '.join(candidate.lane_ids)} -- "
            f"{candidate.distance_nm:.0f} nm, ~{candidate.transit_days:.1f} days, "
            f"risk {candidate.risk}/100."
        )

    def _as_alternative(self, candidate: RouteCandidate) -> RouteAlternative:
        return RouteAlternative(
            lane_ids=candidate.lane_ids,
            distance_nm=candidate.distance_nm,
            transit_days=candidate.transit_days,
            cost_usd=candidate.cost_usd,
            emissions_estimate=candidate.emissions_estimate,
            risk=candidate.risk,
            score=candidate.score,
        )
