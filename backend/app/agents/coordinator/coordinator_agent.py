from app.agents.ingestion.ingestion_agent import IngestionAgent
from app.agents.risk.risk_agent import RiskAgent
from app.agents.route.route_agent import RouteAgent
from app.agents.explanation.explanation_agent import ExplanationAgent
from app.api.dependencies.database import get_db
from app.governance.core import GovernanceEngine
from app.models.governance import AgentExecutionTrace, ApprovalRequest, AgentIdentity
from sqlalchemy.orm import Session
import uuid

class CoordinatorAgent:

    def run(self, db: Session = None, session_id: str = None):
        if db is None:
            db = next(get_db())
        engine = GovernanceEngine(db)
        
        # 0. Set or generate session ID
        if not session_id:
            session_id = str(uuid.uuid4())
            
        # Load existing executions in this session to resume/skip steps
        existing_traces = db.query(AgentExecutionTrace).filter(AgentExecutionTrace.request_id == session_id).all()
        trace_map = {t.agent_id: t for t in existing_traces}
        
        # Helper to check if an agent is quarantined/disabled beforehand
        def check_agent_status(agent_id: str):
            agent = db.query(AgentIdentity).filter(AgentIdentity.id == agent_id).first()
            if agent and agent.status in ["QUARANTINED", "DISABLED"]:
                return agent.status
            return None

        # 1. Ingestion Agent
        trace1 = trace_map.get("ingestion-agent")
        if not trace1:
            q_status = check_agent_status("ingestion-agent")
            if q_status:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Ingestion Agent is {q_status}. Please resolve in governance dashboard."
                }
            try:
                def ingest(data):
                    return IngestionAgent().collect_data_with_confidence()
                trace1, req1 = engine.execute_agent_task("ingestion-agent", "COLLECT", {}, ingest)
                trace1.request_id = session_id
                db.commit()
            except Exception as e:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Ingestion Agent failed: {str(e)}"
                }
        
        event = trace1.output_data
        
        # 2. Risk Agent
        trace2 = trace_map.get("risk-agent")
        if not trace2:
            q_status = check_agent_status("risk-agent")
            if q_status:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Risk Agent is {q_status}. Please resolve in governance dashboard."
                }
            try:
                def calculate_risk(data):
                    risk_agent = RiskAgent()
                    result = risk_agent.calculate_risk(data)
                    confidence = risk_agent.assess_confidence(result["score"], result["scoring_method"])
                    return result, confidence
                trace2, req2 = engine.execute_agent_task("risk-agent", "ANALYZE", event, calculate_risk, parent_execution_id=trace1.id)
                trace2.request_id = session_id
                db.commit()
            except Exception as e:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Risk Agent failed: {str(e)}"
                }
                
        # Check approval status for Risk Agent step
        if trace2.approval_status == "PENDING":
            app_req = db.query(ApprovalRequest).filter(ApprovalRequest.execution_id == trace2.id).first()
            return {
                "status": "PENDING_APPROVAL",
                "session_id": session_id,
                "pending_step": "Risk Assessment Agent",
                "agent_id": "risk-agent",
                "approval_id": app_req.id if app_req else None,
                "reason": trace2.policy_decisions.get("reason") if trace2.policy_decisions else "Risk assessment requires human confirmation."
            }
        elif trace2.approval_status == "REJECTED":
            return {
                "status": "REJECTED",
                "session_id": session_id,
                "error": "Pipeline execution was rejected at Risk Assessment step."
            }
            
        risk = trace2.output_data
        risk_score = risk.get("score", 50) if isinstance(risk, dict) else 50
        
        # 3. Route Agent
        trace3 = trace_map.get("route-agent")
        if not trace3:
            q_status = check_agent_status("route-agent")
            if q_status:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Route Agent is {q_status}. Please resolve in governance dashboard."
                }
            try:
                def suggest_route(data):
                    score = data.get("score", 50) if isinstance(data, dict) else data
                    return RouteAgent().suggest_route(score), 0.9
                trace3, req3 = engine.execute_agent_task("route-agent", "PLAN", risk_score, suggest_route, parent_execution_id=trace2.id)
                trace3.request_id = session_id
                db.commit()
            except Exception as e:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Route Agent failed: {str(e)}"
                }
                
        # Check approval status for Route Agent step
        if trace3.approval_status == "PENDING":
            app_req = db.query(ApprovalRequest).filter(ApprovalRequest.execution_id == trace3.id).first()
            return {
                "status": "PENDING_APPROVAL",
                "session_id": session_id,
                "pending_step": "Route Optimization Agent",
                "agent_id": "route-agent",
                "approval_id": app_req.id if app_req else None,
                "reason": trace3.policy_decisions.get("reason") if trace3.policy_decisions else "Route optimization requires human confirmation."
            }
        elif trace3.approval_status == "REJECTED":
            return {
                "status": "REJECTED",
                "session_id": session_id,
                "error": "Pipeline execution was rejected at Route Planning step."
            }
            
        route = trace3.output_data if trace3 else {"route": "Corridor Beta (Southern Bypass)", "reason": "Avoids severe cyclonic weather system by shifting waypoints 120 nm south."}
        
        # 4. Explanation Agent
        trace4 = trace_map.get("explanation-agent")
        if not trace4:
            q_status = check_agent_status("explanation-agent")
            if q_status:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Explanation Agent is {q_status}. Please resolve in governance dashboard."
                }
            try:
                def explain_route(data):
                    return ExplanationAgent().explain(data, event=event, risk=risk), 0.95
                trace4, req4 = engine.execute_agent_task("explanation-agent", "EXPLAIN", route, explain_route, parent_execution_id=trace3.id if trace3 else None)
                trace4.request_id = session_id
                db.commit()
            except Exception as e:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Explanation Agent failed: {str(e)}"
                }
                
        # Check approval status for Explanation Agent step
        if trace4.approval_status == "PENDING":
            app_req = db.query(ApprovalRequest).filter(ApprovalRequest.execution_id == trace4.id).first()
            return {
                "status": "PENDING_APPROVAL",
                "session_id": session_id,
                "pending_step": "Explanation Agent",
                "agent_id": "explanation-agent",
                "approval_id": app_req.id if app_req else None,
                "reason": trace4.policy_decisions.get("reason") if trace4.policy_decisions else "Explanation generation requires human confirmation."
            }
        elif trace4.approval_status == "REJECTED":
            return {
                "status": "REJECTED",
                "session_id": session_id,
                "error": "Pipeline execution was rejected at Explanation step."
            }
            
        explanation = trace4.output_data if trace4 else "Multi-agent pipeline completed risk assessment and dynamic corridor generation."

        return {
            "status": "COMPLETED",
            "session_id": session_id,
            "event": event,
            "risk_score": risk_score,
            "route": route,
            "explanation": explanation
        }