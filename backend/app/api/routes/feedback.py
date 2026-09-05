from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.feedback.feedback_agent import get_feedback_agent
from app.api.dependencies.auth import get_current_active_user
from app.api.dependencies.database import get_db
from app.models.user import User

router = APIRouter()


class FeedbackCreate(BaseModel):
    execution_id: str
    human_action: str  # APPROVED | REJECTED | MODIFIED
    modification_reason: Optional[str] = None
    predicted_outcome: Optional[str] = None


class OutcomeCreate(BaseModel):
    actual_outcome: str


def _serialize(row) -> dict:
    return {
        "id": row.id,
        "execution_id": row.execution_id,
        "agent_id": row.agent_id,
        "human_action": row.human_action,
        "modification_reason": row.modification_reason,
        "predicted_outcome": row.predicted_outcome,
        "actual_outcome": row.actual_outcome,
        "reviewer_id": row.reviewer_id,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "outcome_recorded_at": row.outcome_recorded_at.isoformat() + "Z" if row.outcome_recorded_at else None,
    }


@router.post("/feedback")
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Records a real human decision against a real agent execution --
    spec section 16. See FeedbackAgent for why this is additive to
    ApprovalRequest, not a duplicate of it.
    """
    try:
        row = get_feedback_agent().record_decision(
            db, payload.execution_id, payload.human_action,
            modification_reason=payload.modification_reason,
            predicted_outcome=payload.predicted_outcome,
            reviewer_id=current_user.username,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return _serialize(row)


@router.patch("/feedback/{feedback_id}/outcome")
def record_outcome(feedback_id: int, payload: OutcomeCreate, db: Session = Depends(get_db)):
    """Records what actually happened, versus what was predicted --
    filled in later, since there's no live mechanism in this system to
    observe it automatically."""
    try:
        row = get_feedback_agent().record_outcome(db, feedback_id, payload.actual_outcome)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return _serialize(row)


@router.get("/feedback")
def list_feedback(agent_id: Optional[str] = None, db: Session = Depends(get_db)):
    rows = get_feedback_agent().list_feedback(db, agent_id=agent_id)
    return [_serialize(r) for r in rows]


@router.get("/feedback/metrics")
def feedback_metrics(db: Session = Depends(get_db)):
    """Real approval/override rate computed from recorded feedback rows
    -- spec section 29's human-AI metrics. Reports null, not a
    fabricated 0%, when zero feedback has been recorded yet.
    """
    return get_feedback_agent().metrics(db)
