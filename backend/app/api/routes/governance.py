from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_current_active_superuser, require_role
from app.core.constants import UserRole
from app.api.dependencies.database import get_db
from app.models.governance import AgentIdentity, AgentExecutionTrace, AuditLog, ApprovalRequest, AgentHealth
from app.models.user import User
from app.governance.registry import get_all_agents
from app.governance.policy import resolve_approval
from app.governance.audit import log_audit_event
from app.governance.trust import compute_trust_score
from typing import List

router = APIRouter()

@router.get("/agents")
def read_agents(db: Session = Depends(get_db)):
    agents = db.query(AgentIdentity).all()
    health_records = {h.agent_id: h for h in db.query(AgentHealth).all()}
    
    result = []
    for a in agents:
        h = health_records.get(a.id)
        result.append({
            "id": a.id,
            "agent_name": a.agent_name,
            "status": a.status,
            "version": a.version,
            "risk_level": a.risk_level,
            "criticality": a.criticality,
            "health": h.status if h else "UNKNOWN",
            "last_active": h.last_heartbeat.isoformat() + "Z" if h and h.last_heartbeat else "Never",
            # Spec section 18 -- real, computed from this same agent's
            # recorded execution/denial/violation/override history, not
            # a static or invented figure. Null when it has never run.
            "trust_score": compute_trust_score(db, a.id),
        })
    return result

@router.get("/executions", dependencies=[Depends(require_role(UserRole.SUPERVISOR))])
def read_executions(db: Session = Depends(get_db)):
    executions = db.query(AgentExecutionTrace).order_by(AgentExecutionTrace.started_at.desc()).limit(50).all()
    return executions

@router.get("/audit", dependencies=[Depends(require_role(UserRole.SUPERVISOR))])
def read_audit(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return logs

@router.get("/approvals")
def read_approvals(db: Session = Depends(get_db)):
    approvals = db.query(ApprovalRequest).filter(ApprovalRequest.status == "PENDING").all()
    
    result = []
    for app in approvals:
        agent = db.query(AgentIdentity).filter(AgentIdentity.id == app.agent_id).first()
        result.append({
            "id": app.id,
            "agent_id": app.agent_id,
            "agent_name": agent.agent_name if agent else app.agent_id,
            "execution_id": app.execution_id,
            "recommendation": app.recommendation,
            "risk_level": app.risk_level,
            "confidence": app.confidence,
            "reason": app.reason,
            "created_at": app.created_at.isoformat() + "Z"
        })
    return result

@router.post("/approvals/{approval_id}/approve")
def approve_request(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    try:
        app = resolve_approval(db, approval_id, "APPROVED", current_user.username)
        log_audit_event(db, "APPROVAL_GRANTED", app.agent_id, app.execution_id, current_user.username, "APPROVAL", "APPROVE", "APPROVED")
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/approvals/{approval_id}/reject")
def reject_request(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    try:
        app = resolve_approval(db, approval_id, "REJECTED", current_user.username)
        log_audit_event(db, "APPROVAL_REJECTED", app.agent_id, app.execution_id, current_user.username, "APPROVAL", "REJECT", "REJECTED")
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/agents/{agent_id}/status")
def update_agent_status(
    agent_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Quarantining or re-enabling an agent halts or resumes the whole
    pipeline, so it is admin-only.
    """
    agent = db.query(AgentIdentity).filter(AgentIdentity.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    old_status = agent.status
    agent.status = status
    db.commit()

    # Record who made the change rather than an anonymous "USER".
    log_audit_event(
        db, "AGENT_STATUS_CHANGED", agent_id, None, current_user.username,
        "AGENT", "UPDATE_STATUS", status,
        f"Status changed from {old_status} to {status} by {current_user.username}",
    )

    return {"status": "success", "agent_id": agent_id, "new_status": status}


@router.get("/activity")
def read_activity(hours: int = 24, db: Session = Depends(get_db)):
    """Hourly agent-execution counts over the last `hours`.

    Backed entirely by rows in agent_executions, so it reflects real
    recorded activity. The Event Monitor timeline previously rendered a
    hardcoded array of invented hourly telemetry counts; this replaces
    that with history the system actually has.

    `recorded_from` lets the UI say how much history exists rather than
    implying a full 24h window it may not have yet — nothing is
    backfilled, so a freshly-started instance legitimately has only a
    few populated buckets.
    """
    hours = max(1, min(hours, 168))
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    window_start = now - timedelta(hours=hours - 1)

    traces = (
        db.query(AgentExecutionTrace)
        .filter(AgentExecutionTrace.started_at >= window_start)
        .all()
    )

    buckets = {
        (window_start + timedelta(hours=i)): {"total": 0, "flagged": 0}
        for i in range(hours)
    }

    for trace in traces:
        if not trace.started_at:
            continue
        key = trace.started_at.replace(minute=0, second=0, microsecond=0)
        bucket = buckets.get(key)
        if bucket is None:
            continue
        bucket["total"] += 1
        # "Flagged" = the run did not complete cleanly on its own: it
        # errored, or governance held/rejected it.
        if trace.error or trace.approval_status in ("PENDING", "REJECTED"):
            bucket["flagged"] += 1

    earliest = db.query(func.min(AgentExecutionTrace.started_at)).scalar()

    return {
        "hours": hours,
        "recorded_from": earliest.isoformat() if earliest else None,
        "total_executions": len(traces),
        "buckets": [
            {
                "hour": hour.isoformat() + "Z",
                "label": hour.strftime("%H:%M"),
                "total": data["total"],
                "flagged": data["flagged"],
            }
            for hour, data in sorted(buckets.items())
        ],
    }


@router.get("/summary", dependencies=[Depends(require_role(UserRole.SUPERVISOR))])
def read_summary(db: Session = Depends(get_db)):
    """Real totals behind the governance tiles. The tiles used to count the
    rows of the latest-50 executions and latest-100 audit lists, so they
    could never read above 50 or 100 however much had happened."""
    since = datetime.utcnow() - timedelta(hours=24)

    def count(query):
        return query.scalar() or 0

    exec_q = db.query(func.count(AgentExecutionTrace.id))
    top_agents = (
        db.query(AgentExecutionTrace.agent_id, func.count(AgentExecutionTrace.id))
        .filter(AgentExecutionTrace.started_at >= since)
        .group_by(AgentExecutionTrace.agent_id)
        .order_by(func.count(AgentExecutionTrace.id).desc())
        .limit(5)
        .all()
    )
    violation_q = db.query(func.count(AuditLog.id)).filter(AuditLog.event_type == "POLICY_VIOLATION")
    latest_violations = (
        db.query(AuditLog).filter(AuditLog.event_type == "POLICY_VIOLATION")
        .order_by(AuditLog.timestamp.desc()).limit(3).all()
    )
    pending = db.query(ApprovalRequest.agent_id, func.count(ApprovalRequest.id)).filter(
        ApprovalRequest.status == "PENDING"
    ).group_by(ApprovalRequest.agent_id).all()

    return {
        "agents_by_status": dict(db.query(AgentIdentity.status, func.count(AgentIdentity.id)).group_by(AgentIdentity.status).all()),
        "executions": {
            "total": count(exec_q),
            "last_24h": count(exec_q.filter(AgentExecutionTrace.started_at >= since)),
            "failed": count(exec_q.filter(AgentExecutionTrace.error.isnot(None))),
            "in_flight": count(exec_q.filter(AgentExecutionTrace.started_at >= datetime.utcnow() - timedelta(minutes=10), AgentExecutionTrace.completed_at.is_(None), AgentExecutionTrace.error.is_(None), or_(AgentExecutionTrace.approval_status.is_(None), AgentExecutionTrace.approval_status != "PENDING"))),
            "awaiting_approval": count(exec_q.filter(AgentExecutionTrace.approval_status == "PENDING")),
            "busiest_24h": [{"agent_id": a, "count": n} for a, n in top_agents],
        },
        "approvals_pending_by_agent": [{"agent_id": a, "count": n} for a, n in pending],
        "violations": {
            "total": count(violation_q),
            "last_24h": count(violation_q.filter(AuditLog.timestamp >= since)),
            "latest": [
                {"at": v.timestamp.isoformat() + "Z", "agent_id": v.agent_id, "reason": v.reason} for v in latest_violations
            ],
        },
    }
