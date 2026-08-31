from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class AgentIdentityBase(BaseModel):
    id: str
    agent_name: str
    description: Optional[str] = None
    agent_type: str
    version: str
    status: str = "ACTIVE"
    owner: Optional[str] = None
    risk_level: str = "LOW"
    criticality: str = "LOW"
    confidence_threshold: float = 0.7
    human_approval_required: bool = False

class AgentIdentity(AgentIdentityBase):
    created_at: datetime
    updated_at: datetime
    class Config:
        orm_mode = True

class AgentCapabilityBase(BaseModel):
    agent_id: str
    capability: str

class AgentPermissionBase(BaseModel):
    agent_id: str
    resource: str
    action: str

class AgentExecutionTraceBase(BaseModel):
    id: str
    agent_id: str
    parent_execution_id: Optional[str] = None
    request_id: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    policy_decisions: Optional[Dict[str, Any]] = None
    approval_status: Optional[str] = None
    error: Optional[str] = None

class AgentExecutionTrace(AgentExecutionTraceBase):
    started_at: datetime
    completed_at: Optional[datetime] = None
    class Config:
        orm_mode = True

class AuditLogBase(BaseModel):
    event_type: str
    agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    actor: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    reason: Optional[str] = None

class AuditLog(AuditLogBase):
    id: int
    timestamp: datetime
    class Config:
        orm_mode = True

class ApprovalRequestBase(BaseModel):
    agent_id: str
    execution_id: str
    recommendation: Optional[Dict[str, Any]] = None
    risk_level: Optional[str] = None
    confidence: Optional[float] = None
    status: str = "PENDING"
    reviewer_id: Optional[str] = None
    reason: Optional[str] = None

class ApprovalRequest(ApprovalRequestBase):
    id: int
    created_at: datetime
    resolved_at: Optional[datetime] = None
    class Config:
        orm_mode = True

class AgentHealthBase(BaseModel):
    agent_id: str
    last_heartbeat: Optional[datetime] = None
    execution_count: int = 0
    success_rate: float = 1.0
    failure_rate: float = 0.0
    average_latency: float = 0.0
    timeout_count: int = 0
    policy_violation_count: int = 0
    denied_actions: int = 0
    status: str = "HEALTHY"

class AgentHealth(AgentHealthBase):
    class Config:
        orm_mode = True
