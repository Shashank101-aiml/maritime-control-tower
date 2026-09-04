from fastapi import APIRouter

from app.twin.digital_twin import fetch_live_corridor_scores, get_digital_twin

router = APIRouter()


@router.get("/twin")
def get_twin_graph():
    """The logistics graph backing Simulation (Slice 08) and Optimization
    (Slice 06) -- 20 ports as nodes, real shipping lanes as edges, each
    edge's risk freshly computed from live sea-state plus real port
    congestion on every request. See app/twin/digital_twin.py's module
    docstring for exactly which fields are real data, which are labeled
    assumptions, and which are distance-based placeholders.
    """
    twin = get_digital_twin()
    corridor_scores = fetch_live_corridor_scores()
    twin.annotate_risk(corridor_scores)

    return {
        **twin.to_dict(),
        "corridors_used": sorted(corridor_scores.keys()),
    }
