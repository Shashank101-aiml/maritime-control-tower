from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, ForeignKey, JSON
from app.database.base import Base

class AgentIdentity(Base):
    __tablename__ = "agents"

    id = Column(String(50), primary_key=True, index=True) # e.g. risk-prediction-v1
    agent_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    agent_type = Column(String(50), nullable=False)
    version = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="ACTIVE") # ACTIVE, PAUSED, DEGRADED, QUARANTINED, DISABLED
    owner = Column(String(50), nullable=True)
    risk_level = Column(String(20), nullable=False, default="LOW") # LOW, MEDIUM, HIGH, CRITICAL
    criticality = Column(String(20), nullable=False, default="LOW")
    confidence_threshold = Column(Float, nullable=False, default=0.7)
    human_approval_required = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentCapability(Base):
    __tablename__ = "agent_capabilities"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(50), ForeignKey("agents.id"))
    capability = Column(String(100), nullable=False)

class AgentPermission(Base):
    __tablename__ = "agent_permissions"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(50), ForeignKey("agents.id"))
    resource = Column(String(100), nullable=False) # e.g. route_graph, weather_api
    action = Column(String(50), nullable=False) # e.g. READ, RUN, GENERATE

class AgentExecutionTrace(Base):
    __tablename__ = "agent_executions"

    id = Column(String(50), primary_key=True, index=True) # execution_id
    agent_id = Column(String(50), ForeignKey("agents.id"))
    parent_execution_id = Column(String(50), nullable=True)
    request_id = Column(String(50), nullable=True)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    policy_decisions = Column(JSON, nullable=True)
    approval_status = Column(String(30), nullable=True) # PENDING, APPROVED, REJECTED, NOT_REQUIRED
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    agent_id = Column(String(50), nullable=True)
    execution_id = Column(String(50), nullable=True)
    actor = Column(String(100), nullable=True)
    resource = Column(String(100), nullable=True)
    action = Column(String(50), nullable=True)
    result = Column(String(50), nullable=True)
    reason = Column(Text, nullable=True)

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(50), ForeignKey("agents.id"))
    execution_id = Column(String(50), ForeignKey("agent_executions.id"))
    recommendation = Column(JSON, nullable=True)
    risk_level = Column(String(20), nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(String(30), default="PENDING") # PENDING, APPROVED, REJECTED
    reviewer_id = Column(String(50), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class Feedback(Base):
    """Spec section 16: closes the loop that ApprovalRequest alone
    doesn't -- ApprovalRequest already records the AI recommendation and
    whether a human approved/rejected it, but not (a) what a human
    changed when they didn't just accept it as-is, or (b) what actually
    happened afterward versus what was predicted. Both are recorded
    here, referencing the same execution rather than duplicating the
    recommendation snapshot ApprovalRequest/AgentExecutionTrace already
    store.
    """
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(String(50), ForeignKey("agent_executions.id"), nullable=False)
    agent_id = Column(String(50), ForeignKey("agents.id"), nullable=False)
    human_action = Column(String(20), nullable=False)  # APPROVED, REJECTED, MODIFIED
    modification_reason = Column(Text, nullable=True)  # required in practice when human_action == MODIFIED
    predicted_outcome = Column(Text, nullable=True)
    actual_outcome = Column(Text, nullable=True)
    reviewer_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    outcome_recorded_at = Column(DateTime, nullable=True)

class AgentHealth(Base):
    __tablename__ = "agent_health"

    agent_id = Column(String(50), ForeignKey("agents.id"), primary_key=True)
    last_heartbeat = Column(DateTime, nullable=True)
    execution_count = Column(Integer, default=0)
    success_rate = Column(Float, default=1.0)
    failure_rate = Column(Float, default=0.0)
    average_latency = Column(Float, default=0.0)
    timeout_count = Column(Integer, default=0)
    policy_violation_count = Column(Integer, default=0)
    denied_actions = Column(Integer, default=0)
    status = Column(String(20), default="HEALTHY") # HEALTHY, DEGRADED, UNAVAILABLE

class AgentCommunicationPolicy(Base):
    __tablename__ = "agent_communication_policies"

    id = Column(Integer, primary_key=True, index=True)
    source_agent_id = Column(String(50), nullable=False)
    target_agent_id = Column(String(50), nullable=False)
    allowed = Column(Boolean, default=True)
