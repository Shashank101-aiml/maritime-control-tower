from sqlalchemy.orm import Session
from app.models.governance import AgentIdentity, AgentPermission, AgentCommunicationPolicy

def check_authorization(db: Session, agent_id: str, resource: str, action: str) -> bool:
    """
    Check if the agent is authorized to perform the action on the resource.

    Least-privilege, per spec section 17: an agent is authorized only
    for a (resource, action) pair explicitly granted in AgentPermission
    (seeded in main.py's seed_governance_agents(), one row per real
    engine.execute_agent_task() call site in this codebase). This used
    to query AgentPermission, discard the result, and unconditionally
    return True -- every execution passed this check regardless of
    whether a permission existed, which is the opposite of what a
    least-privilege authorization check means. Real enforcement now:
    an agent given no explicit grant is denied, not defaulted to allow.
    """
    agent = db.query(AgentIdentity).filter(AgentIdentity.id == agent_id).first()
    if not agent:
        return False

    # If agent is disabled or quarantined, deny all
    if agent.status in ["DISABLED", "QUARANTINED"]:
        return False

    permission = db.query(AgentPermission).filter(
        AgentPermission.agent_id == agent_id,
        AgentPermission.resource == resource,
        AgentPermission.action == action
    ).first()

    return permission is not None

def check_communication(db: Session, source_agent_id: str, target_agent_id: str) -> bool:
    """
    Check if source agent can communicate with target agent.
    """
    policy = db.query(AgentCommunicationPolicy).filter(
        AgentCommunicationPolicy.source_agent_id == source_agent_id,
        AgentCommunicationPolicy.target_agent_id == target_agent_id
    ).first()
    
    if policy:
        return policy.allowed
        
    # Default to true if not explicitly forbidden in this demo,
    # but in a real strict system default should be False.
    return True
