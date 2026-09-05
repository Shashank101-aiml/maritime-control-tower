from sqlalchemy.orm import Session
from app.models.governance import AgentIdentity, ApprovalRequest
import uuid

# Configurable policy rules (spec section 19): each entry is (rule_id,
# condition, reason). Adding, removing, or reordering a rule means
# editing this list, not restructuring evaluate_execution_policy()'s
# control flow -- previously three separate hardcoded if-blocks that
# happened to share a variable. Order matters the same way it did
# before: later matching rules overwrite the reported reason, so the
# last (most specific) match explains a multi-rule trigger.
#
# Each condition takes (agent, confidence) -- the same two pieces of
# live context the three original checks used -- and reason is either
# a plain string or a callable(agent, confidence) -> str for a message
# that depends on the actual values (e.g. the confidence figure).
POLICY_RULES = [
    (
        "explicit_human_approval",
        lambda agent, confidence: agent.human_approval_required,
        "Agent is explicitly configured to require human approval for all actions.",
    ),
    (
        "critical_risk_or_criticality",
        lambda agent, confidence: agent.risk_level == "CRITICAL" or agent.criticality == "CRITICAL",
        "Agent risk/criticality level is CRITICAL.",
    ),
    (
        "confidence_below_threshold",
        lambda agent, confidence: confidence is not None and confidence < agent.confidence_threshold,
        lambda agent, confidence: (
            f"Execution confidence ({confidence:.2f}) is below the agent's threshold "
            f"({agent.confidence_threshold:.2f})."
        ),
    ),
]


def evaluate_execution_policy(db: Session, agent: AgentIdentity, execution_id: str, confidence: float, input_data: dict, output_data: dict):
    """
    Evaluates policy based on agent configuration and execution context.
    Returns: (requires_approval, approval_request_record, reason)
    """
    requires_approval = False
    reason = None

    for _rule_id, condition, message in POLICY_RULES:
        if condition(agent, confidence):
            requires_approval = True
            reason = message(agent, confidence) if callable(message) else message

    # Create an approval request if needed
    approval_request = None
    if requires_approval:
        approval_request = ApprovalRequest(
            agent_id=agent.id,
            execution_id=execution_id,
            recommendation=output_data,
            risk_level=agent.risk_level,
            confidence=confidence,
            reason=reason,
            status="PENDING"
        )
        db.add(approval_request)
        db.commit()
        db.refresh(approval_request)
        
    return requires_approval, approval_request, reason

def resolve_approval(db: Session, approval_id: int, status: str, reviewer_id: str, reason: str = None):
    """
    Resolves an approval request (APPROVED or REJECTED).
    """
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise ValueError(f"Approval request {approval_id} not found.")
        
    approval.status = status
    approval.reviewer_id = reviewer_id
    approval.reason = reason
    from datetime import datetime
    approval.resolved_at = datetime.utcnow()
    
    # Update matching execution trace approval status
    from app.models.governance import AgentExecutionTrace
    trace = db.query(AgentExecutionTrace).filter(AgentExecutionTrace.id == approval.execution_id).first()
    if trace:
        trace.approval_status = status
        
    db.commit()
    db.refresh(approval)
    return approval

