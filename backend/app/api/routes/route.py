import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.agents.route.route_agent import RouteAgent

router = APIRouter()


@router.get("/route/optimize")
def optimize_route(
    origin: str = Query(..., description="Port name, matching a node in the digital twin (see GET /api/twin)."),
    destination: str = Query(..., description="Port name, matching a node in the digital twin."),
    weights: Optional[str] = Query(
        None,
        description=(
            "Override the configured weights, e.g. 'risk:0.6,cost:0.2,delay:0.15,emissions:0.05'. "
            "Uses Settings.ROUTE_OPTIMIZATION_WEIGHTS if omitted."
        ),
    ),
):
    """Real point-to-point route optimization over the digital twin --
    ranked alternatives with actual distance/cost/risk/emissions, each
    a genuine sequence of shipping lanes, not a single fixed label.
    See RouteOptimizer (agents/route/optimizer.py) for how candidates
    are found and scored.
    """
    if origin.strip().lower() == destination.strip().lower():
        raise HTTPException(422, "Origin and destination must be different ports.")

    parsed_weights = None
    if weights:
        try:
            parsed_weights = {
                key.strip(): float(raw)
                for key, raw in (
                    pair.split(":", 1) for pair in weights.split(",") if pair.strip()
                )
            }
        except ValueError:
            raise HTTPException(
                422,
                f"Malformed weights {weights!r}; expected 'risk:0.4,cost:0.25,delay:0.25,emissions:0.1'.",
            )
        unknown = set(parsed_weights) - {"risk", "cost", "delay", "emissions"}
        if unknown:
            raise HTTPException(422, f"Unknown weight(s): {', '.join(sorted(unknown))}. Use risk, cost, delay, emissions.")
        if any(not math.isfinite(w) or w < 0 for w in parsed_weights.values()) or sum(parsed_weights.values()) <= 0:
            raise HTTPException(422, "Weights must be finite, not negative, and add up to more than zero.")

    try:
        recommendation = RouteAgent().suggest_route(origin, destination, weights=parsed_weights)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    return recommendation.model_dump()
