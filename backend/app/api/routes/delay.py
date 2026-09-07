import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents.anomaly.anomaly_agent import get_anomaly_agent
from app.agents.delay.delay_agent import get_delay_agent
from app.api.dependencies.database import get_db
from app.governance.core import GovernanceEngine
from app.models.governance import ApprovalRequest
from app.schemas.delay import DelayPredictionRequest
from app.core.limiter import RATE_LIMIT, limiter

router = APIRouter()


@router.get("/delay/overview")
def get_delay_overview():
    """Real historical shape of the shipment-delay training data --
    overall/per-category late rates, every real value each field
    actually takes, and the real plant->port mapping -- so the manual
    form can offer real dropdown options and prefill a plant's real
    profile instead of a single static, occasionally-invalid example.

    `live_fleet_context` is a real but separate signal: how many of the
    20 named maritime ports the congestion module monitors are
    currently anomalous. It is NOT a feature the delay model was
    trained on -- this dataset's "PORT0x" codes are anonymized and
    unrelated to those real port names (see delay_agent.py) -- it's
    shown purely as situational context, same real number the
    Congestion Prediction page shows.
    """
    agent = get_delay_agent()
    if not agent.has_reference_data:
        raise HTTPException(503, "Delay training data is not available.")

    overview = agent.overview()

    try:
        anomaly_agent = get_anomaly_agent()
        flagged = sum(1 for p in anomaly_agent.known_ports if anomaly_agent.detect(p).anomaly_detected)
        overview["live_fleet_context"] = {"monitored_ports": len(anomaly_agent.known_ports), "flagged_ports": flagged}
    except Exception:
        overview["live_fleet_context"] = None

    return overview


@router.get("/delay/plant/{plant_code}/profile")
def get_delay_plant_profile(plant_code: str):
    agent = get_delay_agent()
    if not agent.has_reference_data:
        raise HTTPException(503, "Delay training data is not available.")
    try:
        return agent.plant_profile(plant_code)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/delay/predict")
@limiter.limit(RATE_LIMIT)
def predict_delay(request: Request, payload: DelayPredictionRequest, db: Session = Depends(get_db)):
    engine = GovernanceEngine(db)
    session_id = str(uuid.uuid4())
    features = payload.model_dump()

    def run(data):
        agent = get_delay_agent()
        result = agent.predict(data)
        return result, result["confidence"]

    try:
        trace, requires_approval = engine.execute_agent_task(
            "delay-agent", "PREDICT", features, run
        )
    except Exception as exc:
        return {"status": "FAILED", "session_id": session_id, "error": str(exc)}

    trace.request_id = session_id
    db.commit()

    if trace.approval_status == "PENDING":
        approval = db.query(ApprovalRequest).filter(ApprovalRequest.execution_id == trace.id).first()
        return {
            "status": "PENDING_APPROVAL",
            "session_id": session_id,
            "agent_id": "delay-agent",
            "approval_id": approval.id if approval else None,
            "reason": trace.policy_decisions.get("reason") if trace.policy_decisions else None,
        }
    if trace.approval_status == "REJECTED":
        return {"status": "REJECTED", "session_id": session_id, "error": "Prediction request was rejected."}

    return {"status": "COMPLETED", "session_id": session_id, "prediction": trace.output_data}
