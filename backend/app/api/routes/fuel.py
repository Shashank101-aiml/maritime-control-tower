import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.agents.fuel.fuel_agent import get_fuel_agent
from app.api.dependencies.database import get_db
from app.fuel.estimator import estimate
from app.fuel.prices import price_client
from app.fuel.reference import (
    DEFAULT_HUB, FUELS, HUBS, LEGACY_ROUTES, PORT_HUB, PRICE_CODES, SHIP_CLASSES, WEATHER_FACTORS,
)
from app.governance.core import GovernanceEngine
from app.models.governance import ApprovalRequest
from app.schemas.fuel import FuelPredictionRequest
from app.core.limiter import RATE_LIMIT, limiter
from app.twin.digital_twin import get_digital_twin

from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/fuel/predict")
@limiter.limit(RATE_LIMIT)
def predict_fuel(request: Request, payload: FuelPredictionRequest, db: Session = Depends(get_db)):
    engine = GovernanceEngine(db)
    session_id = str(uuid.uuid4())
    features = payload.model_dump()

    def run(data):
        result = estimate(data, get_fuel_agent(), price_client)
        return result, result["confidence"]

    try:
        trace, requires_approval = engine.execute_agent_task(
            "fuel-agent", "PREDICT", features, run
        )
    except ValueError as exc:
        return {"status": "FAILED", "session_id": session_id, "error": str(exc)}
    except Exception:
        # Anything else is ours to fix, not the caller's to read: log it in full
        # and give them a message that leaks nothing (database errors, paths).
        logger.exception("Fuel estimate failed")
        return {"status": "FAILED", "session_id": session_id, "error": "The estimate could not be produced. Please try again."}

    trace.request_id = session_id
    db.commit()

    if trace.approval_status == "PENDING":
        approval = db.query(ApprovalRequest).filter(ApprovalRequest.execution_id == trace.id).first()
        return {
            "status": "PENDING_APPROVAL",
            "session_id": session_id,
            "agent_id": "fuel-agent",
            "approval_id": approval.id if approval else None,
            "reason": trace.policy_decisions.get("reason") if trace.policy_decisions else None,
        }
    if trace.approval_status == "REJECTED":
        return {"status": "REJECTED", "session_id": session_id, "error": "Prediction request was rejected."}

    return {"status": "COMPLETED", "session_id": session_id, "prediction": trace.output_data}


def _route_label(lane_id: str, port_a: str, port_b: str) -> str:
    via = " via Suez" if "suez" in lane_id else " via Cape of Good Hope" if "cape" in lane_id else ""
    return f"{port_a} - {port_b}{via}"


@router.get("/fuel/options")
def fuel_options():
    """Everything the form offers: ship classes, fuels (and whether a live price
    exists for each), routes with their distance and nearest price hub, and hubs."""
    twin = get_digital_twin()
    routes = sorted(
        (
            {
                "value": attrs["lane_id"],
                "label": _route_label(attrs["lane_id"], attrs["lane_port_a"], attrs["lane_port_b"]),
                "distance_nm": attrs["distance_nm"],
                "hub": PORT_HUB.get(attrs["lane_port_a"], DEFAULT_HUB),
                "group": "Shipping lanes",
            }
            for _, _, attrs in twin.graph.edges(data=True)
        ),
        key=lambda r: r["label"],
    )
    routes += [{"value": name, "label": name, "distance_nm": None, "hub": DEFAULT_HUB, "group": "Niger Delta dataset"} for name in LEGACY_ROUTES]
    return {
        "ship_types": [{"value": s["value"], "group": s["group"]} for s in SHIP_CLASSES],
        "fuel_types": [
            {"value": key, "label": props["label"], "priced": PRICE_CODES.get(key) is not None and price_client.configured}
            for key, props in FUELS.items()
        ],
        "routes": routes,
        "hubs": [{"value": code, "label": name} for code, name in HUBS.items()],
        "weather": list(WEATHER_FACTORS),
        "prices_configured": price_client.configured,
    }


@router.get("/fuel/prices")
def fuel_prices(hub: str = Query(DEFAULT_HUB)):
    """Current bunker price for every fuel at one hub, from the live price service."""
    if hub not in HUBS:
        raise HTTPException(404, f"Unknown price hub '{hub}'.")
    return {"hub": hub, "hub_name": HUBS[hub], "configured": price_client.configured, "prices": price_client.all_prices(hub)}
