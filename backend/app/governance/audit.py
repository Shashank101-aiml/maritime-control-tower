from sqlalchemy.orm import Session
from app.models.governance import AuditLog
from datetime import datetime

def log_audit_event(
    db: Session,
    event_type: str,
    agent_id: str = None,
    execution_id: str = None,
    actor: str = None,
    resource: str = None,
    action: str = None,
    result: str = None,
    reason: str = None
):
    log_entry = AuditLog(
        timestamp=datetime.utcnow(),
        event_type=event_type,
        agent_id=agent_id,
        execution_id=execution_id,
        actor=actor or agent_id or "SYSTEM",
        resource=resource,
        action=action,
        result=result,
        reason=reason
    )
    db.add(log_entry)
    db.commit()
    return log_entry
