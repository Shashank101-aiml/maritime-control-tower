from fastapi import APIRouter
from app.agents.coordinator.coordinator_agent import CoordinatorAgent

router = APIRouter()


@router.get("/recommendations")
def get_recommendations():
    """Returns the coordinator's routing recommendation.

    The workflow does not always reach COMPLETED -- a governance policy can
    pause it for human approval (PENDING_APPROVAL) or stop it outright
    (REJECTED / FAILED). Those responses carry no risk_score/route/
    explanation keys, so the status is checked before reading them; the
    endpoint previously assumed completion and raised KeyError
    ('risk_score'), returning a 500 whenever a gate was open.
    """
    result = CoordinatorAgent().run()
    status = result.get("status")

    if status != "COMPLETED":
        return {
            "status": status,
            "timestamp": "Real-time AI Analysis",
            "action_required": status == "PENDING_APPROVAL",
            "primary_recommendation": result.get("reason")
            or result.get("error")
            or "The agent workflow did not complete.",
            "suggested_route": None,
            "assessed_risk": None,
            "pending_step": result.get("pending_step"),
            "session_id": result.get("session_id"),
        }

    risk_score = result.get("risk_score")
    return {
        "status": "SUCCESS",
        "timestamp": "Real-time AI Analysis",
        "action_required": risk_score is not None and risk_score > 50,
        "primary_recommendation": result.get("explanation"),
        "suggested_route": result.get("route"),
        "assessed_risk": risk_score,
    }
