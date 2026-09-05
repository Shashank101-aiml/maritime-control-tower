"""Real human-AI interaction outcomes (spec section 16). ApprovalRequest
(app/models/governance.py) already records the AI recommendation and
whether a human approved/rejected it -- what's missing, and what this
closes, is (a) what a human changed when they didn't just accept a
recommendation as-is, and (b) what actually happened afterward versus
what was predicted. Both reference the same AgentExecutionTrace rather
than duplicating the recommendation snapshot that already exists there.

Powers the section 29 human-AI metrics (approval rate, override rate)
from real recorded rows -- a metric with zero feedback rows is honestly
reported as unavailable, not a fabricated percentage.
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.governance import AgentExecutionTrace, Feedback

VALID_ACTIONS = ("APPROVED", "REJECTED", "MODIFIED")


class FeedbackAgent:
    def record_decision(
        self,
        db: Session,
        execution_id: str,
        human_action: str,
        modification_reason: Optional[str] = None,
        predicted_outcome: Optional[str] = None,
        reviewer_id: Optional[str] = None,
    ) -> Feedback:
        if human_action not in VALID_ACTIONS:
            raise ValueError(f"human_action must be one of {VALID_ACTIONS}, got {human_action!r}.")
        if human_action == "MODIFIED" and not modification_reason:
            raise ValueError("modification_reason is required when human_action is MODIFIED.")

        trace = db.query(AgentExecutionTrace).filter(AgentExecutionTrace.id == execution_id).first()
        if not trace:
            raise ValueError(f"No execution found with id {execution_id!r}.")

        # The agent's own recorded output is the real "prediction" --
        # not re-typed by the caller unless they want to say something
        # more specific.
        if predicted_outcome is None:
            output = trace.output_data or {}
            predicted_outcome = output.get("recommendation") or output.get("reason") or output.get("route")

        feedback = Feedback(
            execution_id=execution_id,
            agent_id=trace.agent_id,
            human_action=human_action,
            modification_reason=modification_reason,
            predicted_outcome=predicted_outcome,
            reviewer_id=reviewer_id,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback

    def record_outcome(self, db: Session, feedback_id: int, actual_outcome: str) -> Feedback:
        feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise ValueError(f"No feedback row with id {feedback_id!r}.")
        feedback.actual_outcome = actual_outcome
        feedback.outcome_recorded_at = datetime.utcnow()
        db.commit()
        db.refresh(feedback)
        return feedback

    def list_feedback(self, db: Session, agent_id: Optional[str] = None) -> List[Feedback]:
        query = db.query(Feedback).order_by(Feedback.created_at.desc())
        if agent_id:
            query = query.filter(Feedback.agent_id == agent_id)
        return query.all()

    def metrics(self, db: Session) -> Dict[str, Optional[float]]:
        rows = db.query(Feedback).all()
        total = len(rows)
        if total == 0:
            return {"total": 0, "approval_rate": None, "override_rate": None, "outcomes_recorded": 0}

        approved = sum(1 for r in rows if r.human_action == "APPROVED")
        overridden = sum(1 for r in rows if r.human_action in ("REJECTED", "MODIFIED"))
        outcomes_recorded = sum(1 for r in rows if r.actual_outcome is not None)
        return {
            "total": total,
            "approval_rate": round(approved / total, 3),
            "override_rate": round(overridden / total, 3),
            "outcomes_recorded": outcomes_recorded,
        }


_shared_agent: Optional[FeedbackAgent] = None


def get_feedback_agent() -> FeedbackAgent:
    global _shared_agent
    if _shared_agent is None:
        _shared_agent = FeedbackAgent()
    return _shared_agent
