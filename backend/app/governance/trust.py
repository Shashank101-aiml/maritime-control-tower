"""Agent trust score (spec section 18): one number combining real
recorded reliability and governance signals AgentHealth already
tracks, plus real human-override data from Feedback (Slice 11) when
available -- not an invented reputation metric with no data behind it.

trust = success_rate * (1 - denial_rate) * (1 - violation_rate) * (1 - override_rate)

- success_rate: AgentHealth's own running rate, updated on every
  execute_agent_task() call.
- denial_rate / violation_rate: denied_actions / policy_violation_count
  as a share of execution_count -- raw counts aren't comparable across
  agents with very different execution volumes, so both are
  normalized into rates first.
- override_rate: share of that agent's recorded Feedback rows where a
  human rejected or modified the recommendation rather than approving
  it as-is. Omitted (factor of 1, no penalty) when the agent has no
  feedback rows yet -- absence of data is not evidence of distrust.

Returns None (not a fabricated 0 or 1) for an agent with zero recorded
executions -- there is no honest trust score to report yet.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.governance import AgentHealth, Feedback


def compute_trust_score(db: Session, agent_id: str) -> Optional[float]:
    health = db.query(AgentHealth).filter(AgentHealth.agent_id == agent_id).first()
    if not health or not health.execution_count:
        return None

    denial_rate = health.denied_actions / health.execution_count
    violation_rate = health.policy_violation_count / health.execution_count
    trust = health.success_rate * (1 - denial_rate) * (1 - violation_rate)

    feedback_rows = db.query(Feedback).filter(Feedback.agent_id == agent_id).all()
    if feedback_rows:
        overridden = sum(1 for f in feedback_rows if f.human_action in ("REJECTED", "MODIFIED"))
        override_rate = overridden / len(feedback_rows)
        trust *= (1 - override_rate)

    return round(max(0.0, min(1.0, trust)), 3)
