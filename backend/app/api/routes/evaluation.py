import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.models.governance import AgentExecutionTrace, ApprovalRequest, Feedback

router = APIRouter()

METRICS_DIR = Path(__file__).resolve().parents[4] / "models" / "saved_models"
MODEL_NAMES = ["congestion", "delay", "fuel", "anomaly"]


@router.get("/evaluation/model-metrics")
def get_model_metrics():
    """Real persisted training metrics per model (spec sections 29/30).
    Each pipeline/train_*_model.py script used to print its ROC-AUC/
    PR-AUC/MAE/etc. and lose them the moment the process exited -- this
    reads back exactly what each script actually computed and saved
    (evaluation_utils.save_metrics), including the real no-skill/mean
    baseline every script now records alongside its trained model's
    result. A model not yet (re)trained since this file existed reports
    null, not a fabricated placeholder.
    """
    result = {}
    for name in MODEL_NAMES:
        path = METRICS_DIR / f"{name}_metrics.json"
        result[name] = json.loads(path.read_text()) if path.exists() else None
    return result


@router.get("/evaluation/governance-impact")
def get_governance_impact(db: Session = Depends(get_db)):
    """Spec section 30's "multi-agent without governance vs. full
    system" comparison, made of real counts rather than a simulated
    run: every execution recorded would have proceeded automatically
    with no human-in-the-loop gate at all; gated_for_approval is how
    many were actually held for a human decision instead, and
    human_overrides is how many recorded Feedback rows (Slice 11) a
    reviewer rejected or changed rather than accepting as-is.
    """
    total_executions = db.query(AgentExecutionTrace).count()
    gated_for_approval = db.query(ApprovalRequest).count()
    approved = db.query(ApprovalRequest).filter(ApprovalRequest.status == "APPROVED").count()
    rejected_at_gate = db.query(ApprovalRequest).filter(ApprovalRequest.status == "REJECTED").count()
    pending_approval = db.query(ApprovalRequest).filter(ApprovalRequest.status == "PENDING").count()

    total_feedback = db.query(Feedback).count()
    human_overrides = db.query(Feedback).filter(Feedback.human_action.in_(["REJECTED", "MODIFIED"])).count()

    return {
        "total_executions": total_executions,
        "gated_for_approval": gated_for_approval,
        "gated_rate": round(gated_for_approval / total_executions, 4) if total_executions else None,
        "approved": approved,
        "rejected_at_gate": rejected_at_gate,
        "pending_approval": pending_approval,
        "feedback_recorded": total_feedback,
        "human_overrides": human_overrides,
        "override_rate": round(human_overrides / total_feedback, 4) if total_feedback else None,
        "note": (
            "Without governance, all total_executions would have proceeded automatically. "
            "gated_for_approval were actually held for a human decision instead of proceeding "
            "unreviewed; human_overrides is how many recorded decisions a reviewer rejected or "
            "changed rather than accepting as-is."
        ),
    }
