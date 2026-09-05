from app.agents.ingestion.ingestion_agent import IngestionAgent
from app.agents.risk.risk_agent import RiskAgent
from app.agents.route.route_agent import RouteAgent
from app.agents.decision.decision_agent import DecisionAgent
from app.agents.explanation.explanation_agent import ExplanationAgent
from app.api.dependencies.database import get_db
from app.governance.core import GovernanceEngine
from app.models.governance import AgentExecutionTrace, ApprovalRequest, AgentIdentity
from app.schemas.agent_io import Decision, IngestedEvent, RiskAssessment, RouteRecommendation
from app.twin.digital_twin import fetch_live_corridor_scores, get_digital_twin
from sqlalchemy.orm import Session
import uuid

# Adaptive orchestration (spec section 21): a genuinely calm/nominal
# event needs no route change or decision -- running the full
# route-optimization -> decision -> explanation chain for it is the
# "fixed sequential pipeline regardless of what's actually happening"
# the spec calls out as the thing to avoid. 20 sits below the sample
# fixture's own real score (28, "Cyclone" -- Data/features/... derived,
# not tuned to dodge a test) and below the frontend's own NORMAL/
# ELEVATED boundary (35, types/Risk.js's getRiskLevel) -- a real
# "nominal" band, not a threshold picked to make a particular event
# take one path or the other.
ADAPTIVE_COMPLEXITY_THRESHOLD = 20

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

        # Adaptive orchestration (spec section 21): a nominal-risk event
        # is "simple" -- there is no elevated corridor to route around
        # and no trade-off for the Decision Agent to weigh, so running
        # route optimization, decision, and explanation for it would be
        # pure overhead on a fixed chain that ignores what the risk
        # agent actually found. Skips straight to a real, honest
        # completion instead of a fabricated route/decision.
        if risk_score < ADAPTIVE_COMPLEXITY_THRESHOLD:
            return {
                "status": "COMPLETED",
                "session_id": session_id,
                "event": event.model_dump(),
                "risk_score": risk_score,
                "route": None,
                "decision": None,
                "decision_execution_id": None,
                "explanation": (
                    f"Risk score {risk_score}/100 is nominal -- no elevated corridor to route around "
                    "and no decision trade-off to weigh. Route optimization, decision, and explanation "
                    "steps were skipped (adaptive orchestration, spec section 21)."
                ),
                "adaptive_pipeline": "simple",
            }

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
                # There is no specific vessel/shipment in this pipeline's
                # data -- inventing an origin/destination would be exactly
                # the kind of fabrication this project avoids elsewhere.
                # Instead: find the real shipping lane most exposed right
                # now (same live-annotated twin GET /api/twin uses) and
                # route-optimize around that -- a real, different, and
                # honestly-answerable question.
                twin = get_digital_twin()
                twin.annotate_risk(fetch_live_corridor_scores())
                most_at_risk = twin.most_at_risk_edge()
                if most_at_risk is None:
                    return {
                        "status": "FAILED",
                        "session_id": session_id,
                        "error": "Route Agent failed: the digital twin has no lanes to route through."
                    }
                origin, destination, _lane_id = most_at_risk

                def suggest_route(data):
                    return RouteAgent().suggest_route(data["origin"], data["destination"]), 0.9
                trace3, req3 = engine.execute_agent_task(
                    "route-agent", "PLAN",
                    {"origin": origin, "destination": destination},
                    suggest_route, parent_execution_id=trace2.id,
                )
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

        # 4. Decision Agent -- turns the ranked route into a structured
        # trade-off (spec Slice 07/§13): what changes versus the most
        # obvious alternative, and whether that change is confident
        # enough to act on without a human sign-off.
        trace4 = trace_map.get("decision-agent")
        if not trace4:
            q_status = check_agent_status("decision-agent")
            if q_status:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Decision Agent is {q_status}. Please resolve in governance dashboard."
                }
            try:
                def make_decision(data):
                    decision = DecisionAgent().decide(data)
                    return decision, decision.confidence
                trace4, req4 = engine.execute_agent_task("decision-agent", "DECIDE", route, make_decision, parent_execution_id=trace3.id)
                trace4.request_id = session_id
                db.commit()
            except Exception as e:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Decision Agent failed: {str(e)}"
                }

        # Check approval status for Decision Agent step
        if trace4.approval_status == "PENDING":
            app_req = db.query(ApprovalRequest).filter(ApprovalRequest.execution_id == trace4.id).first()
            return {
                "status": "PENDING_APPROVAL",
                "session_id": session_id,
                "pending_step": "Decision Agent",
                "agent_id": "decision-agent",
                "approval_id": app_req.id if app_req else None,
                "reason": trace4.policy_decisions.get("reason") if trace4.policy_decisions else "Decision requires human confirmation."
            }
        elif trace4.approval_status == "REJECTED":
            return {
                "status": "REJECTED",
                "session_id": session_id,
                "error": "Pipeline execution was rejected at Decision step."
            }

        decision = Decision.model_validate(trace4.output_data)

        # 5. Explanation Agent
        trace5 = trace_map.get("explanation-agent")
        if not trace5:
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
                trace5, req5 = engine.execute_agent_task("explanation-agent", "EXPLAIN", route, explain_route, parent_execution_id=trace4.id)
                trace5.request_id = session_id
                db.commit()
            except Exception as e:
                return {
                    "status": "FAILED",
                    "session_id": session_id,
                    "error": f"Explanation Agent failed: {str(e)}"
                }

        # Check approval status for Explanation Agent step
        if trace5.approval_status == "PENDING":
            app_req = db.query(ApprovalRequest).filter(ApprovalRequest.execution_id == trace5.id).first()
            return {
                "status": "PENDING_APPROVAL",
                "session_id": session_id,
                "pending_step": "Explanation Agent",
                "agent_id": "explanation-agent",
                "approval_id": app_req.id if app_req else None,
                "reason": trace5.policy_decisions.get("reason") if trace5.policy_decisions else "Explanation generation requires human confirmation."
            }
        elif trace5.approval_status == "REJECTED":
            return {
                "status": "REJECTED",
                "session_id": session_id,
                "error": "Pipeline execution was rejected at Explanation step."
            }

        # Same reasoning as the route fallback above: trace5 is always set
        # here, so the old "else <fabricated sentence>" branch could never
        # run. explain() returns a plain string, so no rehydration needed.
        explanation = trace5.output_data

        return {
            "status": "COMPLETED",
            "session_id": session_id,
            "event": event.model_dump(),
            "risk_score": risk_score,
            "route": route.model_dump(),
            "decision": decision.model_dump(),
            # Lets a caller record real feedback (Slice 11) against the
            # exact execution that produced this decision.
            "decision_execution_id": trace4.id,
            "explanation": explanation,
            "adaptive_pipeline": "full",
        }
