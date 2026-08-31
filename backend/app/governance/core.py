from sqlalchemy.orm import Session
from app.models.governance import AgentIdentity, AgentExecutionTrace, AgentHealth
from app.governance.registry import record_heartbeat
from app.governance.authorization import check_authorization
from app.governance.policy import evaluate_execution_policy
from app.governance.audit import log_audit_event
from datetime import datetime
import uuid

class GovernanceEngine:
    def __init__(self, db: Session):
        self.db = db

    def execute_agent_task(self, agent_id: str, action: str, input_data: dict, task_func, parent_execution_id: str = None):
        """
        Wraps an agent execution with governance checks and tracing.
        """
        # 1. Identity & Health Check
        agent = self.db.query(AgentIdentity).filter(AgentIdentity.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not registered in governance registry.")
            
        record_heartbeat(self.db, agent_id)
        
        if agent.status in ["QUARANTINED", "DISABLED"]:
            log_audit_event(self.db, "POLICY_VIOLATION", agent_id, None, None, action, "EXECUTE", "DENIED", f"Agent is {agent.status}")
            raise PermissionError(f"Agent {agent_id} is {agent.status} and cannot execute tasks.")

        # 2. Authorization Check
        if not check_authorization(self.db, agent_id, action, "EXECUTE"):
            log_audit_event(self.db, "TOOL_ACCESS_DENIED", agent_id, None, None, action, "EXECUTE", "DENIED", "Unauthorized action.")
            health = self.db.query(AgentHealth).filter(AgentHealth.agent_id == agent_id).first()
            if health:
                health.denied_actions += 1
                self.db.commit()
            raise PermissionError(f"Agent {agent_id} not authorized to execute {action}.")

        # 3. Create Execution Trace
        execution_id = str(uuid.uuid4())
        trace = AgentExecutionTrace(
            id=execution_id,
            agent_id=agent_id,
            parent_execution_id=parent_execution_id,
            input_data=input_data,
            started_at=datetime.utcnow()
        )
        self.db.add(trace)
        self.db.commit()
        
        log_audit_event(self.db, "AGENT_STARTED", agent_id, execution_id, agent_id, action, "EXECUTE", "STARTED")

        # 4. Execute Task (The actual agent logic)
        try:
            output_data, confidence = task_func(input_data)
            trace.output_data = output_data
            trace.confidence = confidence
        except Exception as e:
            trace.error = str(e)
            trace.completed_at = datetime.utcnow()
            self.db.commit()
            
            log_audit_event(self.db, "AGENT_FAILED", agent_id, execution_id, agent_id, action, "EXECUTE", "FAILED", str(e))
            
            health = self.db.query(AgentHealth).filter(AgentHealth.agent_id == agent_id).first()
            if health:
                health.failure_rate = (health.failure_rate * health.execution_count + 1) / (health.execution_count + 1)
                health.execution_count += 1
                self.db.commit()
                
            raise e

        # 5. Policy Evaluation (Human-in-the-loop check)
        requires_approval, approval_request, reason = evaluate_execution_policy(
            self.db, agent, execution_id, confidence, input_data, output_data
        )
        
        if requires_approval:
            trace.approval_status = "PENDING"
            trace.policy_decisions = {"requires_approval": True, "reason": reason}
            log_audit_event(self.db, "APPROVAL_REQUESTED", agent_id, execution_id, agent_id, action, "EVALUATE_POLICY", "PENDING_APPROVAL", reason)
        else:
            trace.approval_status = "NOT_REQUIRED"
            trace.policy_decisions = {"requires_approval": False}
            log_audit_event(self.db, "AGENT_COMPLETED", agent_id, execution_id, agent_id, action, "EXECUTE", "COMPLETED")

        trace.completed_at = datetime.utcnow()
        
        # Update Health
        health = self.db.query(AgentHealth).filter(AgentHealth.agent_id == agent_id).first()
        if health:
            health.success_rate = (health.success_rate * health.execution_count + 1) / (health.execution_count + 1)
            health.execution_count += 1
            self.db.commit()

        self.db.commit()
        self.db.refresh(trace)
        
        return trace, requires_approval
