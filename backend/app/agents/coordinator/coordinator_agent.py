from app.agents.ingestion.ingestion_agent import IngestionAgent
from app.agents.risk.risk_agent import RiskAgent
from app.agents.route.route_agent import RouteAgent
from app.agents.explanation.explanation_agent import ExplanationAgent
from app.api.dependencies.database import get_db
from app.governance.core import GovernanceEngine
from app.models.governance import AgentExecutionTrace, ApprovalRequest, AgentIdentity
from app.schemas.agent_io import IngestedEvent, RiskAssessment, RouteRecommendation
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

        # GovernanceEngine stores every trace's output as plain JSON (it has
        # to -- that's the DB column type), so rehydrate it into the typed
        # contract here. This is the hand-off risk_agent actually consumes.
        event = IngestedEvent.model_validate(trace1.output_data)

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
                    confidence = risk_agent.assess_confidence(result.score, result.scoring_method)
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

        # score is a required field on RiskAssessment -- if the risk agent
        # ever fails to produce one, this raises here rather than silently
        # treating a broken risk agent as "medium risk" (previously
        # `risk.get("score", 50)`).
        risk = RiskAssessment.model_validate(trace2.output_data)
        risk_score = risk.score

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
                    return RouteRecommendation(**RouteAgent().suggest_route(data)), 0.9
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

        # trace3 is always set by this point (either resumed from trace_map
        # or just created above -- every earlier return covers the cases
        # where it wouldn't be), so there is no real "no route" case to
        # fall back for. The previous fallback here was a hardcoded
        # "Corridor Beta (Southern Bypass)" that could never actually run,
        # which is worse than no fallback: it looked like a real decision.
        route = RouteRecommendation.model_validate(trace3.output_data)

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
                    # ExplanationAgent/PromptBuilder are dict-based internally
                    # and unaffected by this slice -- convert at the call site.
                    return ExplanationAgent().explain(
                        data.model_dump(), event=event.model_dump(), risk=risk.model_dump()
                    ), 0.95
                trace4, req4 = engine.execute_agent_task("explanation-agent", "EXPLAIN", route, explain_route, parent_execution_id=trace3.id)
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

        # Same reasoning as the route fallback above: trace4 is always set
        # here, so the old "else <fabricated sentence>" branch could never
        # run. explain() returns a plain string, so no rehydration needed.
        explanation = trace4.output_data

        return {
            "status": "COMPLETED",
            "session_id": session_id,
            "event": event.model_dump(),
            "risk_score": risk_score,
            "route": route.model_dump(),
            "explanation": explanation
        }
