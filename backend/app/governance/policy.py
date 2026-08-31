from sqlalchemy.orm import Session
from app.models.governance import AgentIdentity, ApprovalRequest
import uuid

def evaluate_execution_policy(db: Session, agent: AgentIdentity, execution_id: str, confidence: float, input_data: dict, output_data: dict):
    """
    Evaluates policy based on agent configuration and execution context.
    Returns: (requires_approval, approval_request_record, reason)
    """
    requires_approval = False
    reason = None
    
    # 1. Check explicit agent config
    if agent.human_approval_required:
        requires_approval = True
        reason = "Agent is explicitly configured to require human approval for all actions."
        
    # 2. Check risk and criticality thresholds
    if agent.risk_level in ["CRITICAL"] or agent.criticality in ["CRITICAL"]:
        requires_approval = True
        reason = "Agent risk/criticality level is CRITICAL."
        
    # 3. Check confidence
    if confidence is not None and confidence < agent.confidence_threshold:
        requires_approval = True
        reason = f"Execution confidence ({confidence:.2f}) is below the agent's threshold ({agent.confidence_threshold:.2f})."
        
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

