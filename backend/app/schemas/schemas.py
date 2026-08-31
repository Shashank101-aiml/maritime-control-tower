from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class TelemetryEvent(BaseModel):
    event_type: str
    location: str
    severity: str
    timestamp: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class RiskAssessment(BaseModel):
    risk_score: int
    hazard_level: str
    warnings: List[str]

class RouteSuggestion(BaseModel):
    route: str
    reason: str
    estimated_time_hours: Optional[float] = None
    waypoints: Optional[List[str]] = None

class AgentExplanation(BaseModel):
    summary: str
    confidence_score: float = 0.95

class AgentStatus(BaseModel):
    agent_name: str
    role: str
    status: str
    last_active: str

class DashboardSummary(BaseModel):
    active_vessels: int
    active_alerts: int
    average_fleet_risk: int
    recent_events: List[Dict[str, Any]]
    system_status: str

class WorkflowResult(BaseModel):
    event: Dict[str, Any]
    risk_score: int
    route: Dict[str, Any]
    explanation: str
