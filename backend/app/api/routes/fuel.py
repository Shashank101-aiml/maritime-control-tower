import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.agents.fuel.fuel_agent import get_fuel_agent
from app.api.dependencies.database import get_db
from app.governance.core import GovernanceEngine
from app.models.governance import ApprovalRequest
from app.schemas.fuel import FuelPredictionRequest
from app.core.limiter import RATE_LIMIT, limiter

router = APIRouter()


@router.post("/fuel/predict")
@limiter.limit(RATE_LIMIT)
def predict_fuel(request: Request, payload: FuelPredictionRequest, db: Session = Depends(get_db)):
    engine = GovernanceEngine(db)
    session_id = str(uuid.uuid4())
    features = payload.model_dump()

    def run(data):
        agent = get_fuel_agent()
        result = agent.predict(data)
        return result, result["confidence"]

    try:
        trace, requires_approval = engine.execute_agent_task(
            "fuel-agent", "PREDICT", features, run
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
            "agent_id": "fuel-agent",
            "approval_id": approval.id if approval else None,
            "reason": trace.policy_decisions.get("reason") if trace.policy_decisions else None,
        }
    if trace.approval_status == "REJECTED":
        return {"status": "REJECTED", "session_id": session_id, "error": "Prediction request was rejected."}

    return {"status": "COMPLETED", "session_id": session_id, "prediction": trace.output_data}
