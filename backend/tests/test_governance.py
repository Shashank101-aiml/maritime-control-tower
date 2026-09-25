

def test_summary_counts_everything_not_just_the_latest_rows():
    """The governance tiles used to count a capped list (latest 50 / 100 rows)."""
    from datetime import datetime, timedelta

    from app.models.governance import AgentExecutionTrace, AgentIdentity, AuditLog

    from tests.fleet_support import make_engine_and_session

    Session = make_engine_and_session()
    db = Session()
    db.add(AgentIdentity(id="risk-agent", agent_name="Risk Agent", agent_type="ANALYZER", version="v1"))
    db.commit()
    now = datetime.utcnow()
    for i in range(120):
        db.add(AgentExecutionTrace(id=f"e{i}", agent_id="risk-agent", started_at=now - timedelta(hours=i),
                                   completed_at=now, approval_status="NOT_REQUIRED"))
    db.add(AgentExecutionTrace(id="stuck", agent_id="risk-agent", started_at=now))
    db.add(AgentExecutionTrace(id="waiting", agent_id="risk-agent", started_at=now, approval_status="PENDING"))
    db.add(AgentExecutionTrace(id="bad", agent_id="risk-agent", started_at=now, error="boom"))
    for i in range(150):
        db.add(AuditLog(event_type="POLICY_VIOLATION", agent_id="risk-agent", timestamp=now - timedelta(hours=i), reason="quarantined"))
    db.commit()

    from app.api.routes.governance import read_summary

    body = read_summary(db)
    assert body["executions"]["total"] == 123 and body["executions"]["last_24h"] == 27
    assert body["executions"]["in_flight"] == 1 and body["executions"]["awaiting_approval"] == 1
    assert body["executions"]["failed"] == 1
    assert body["violations"]["total"] == 150 and body["violations"]["last_24h"] == 24  # > the old 100-row cap
    assert len(body["violations"]["latest"]) == 3
