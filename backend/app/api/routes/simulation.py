from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.agents.simulation.simulation_agent import SCENARIOS, SimulationAgent

router = APIRouter()


@router.get("/simulate")
def simulate_scenario(
    origin: str = Query(..., description="Port name, matching a node in the digital twin (see GET /api/twin)."),
    destination: str = Query(..., description="Port name, matching a node in the digital twin."),
    corridor: str = Query(..., description="Monitored corridor name to simulate disruption at (see GET /api/twin's edges' waypoints, or GET /api/conditions)."),
    scenario: str = Query("MODERATE", description=f"One of {SCENARIOS}."),
    weights: Optional[str] = Query(
        None,
        description="Override the configured weights, e.g. 'risk:0.6,cost:0.2,delay:0.15,emissions:0.05'.",
    ),
):
    """What the real route optimizer would recommend if the given
    monitored corridor's conditions worsen (MODERATE) or the corridor
    became fully impassable (SEVERE), versus today's real baseline --
    see SimulationAgent for exactly what each scenario changes on the
    digital twin (a copy, never the shared live one).
    """
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

    try:
        result = SimulationAgent().simulate(origin, destination, corridor, scenario, weights=parsed_weights)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    return result.model_dump()
