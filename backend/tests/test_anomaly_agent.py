"""Tests for the Anomaly Detection Agent (Slice 09): real Isolation
Forest scoring over each port's own historical congestion data.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.anomaly.anomaly_agent import AnomalyAgent
from app.main import app

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist


class TestAnomalyAgent:
    def test_model_loaded_from_the_real_trained_artifact(self):
        agent = AnomalyAgent()
        assert agent.is_available, "Run pipeline/train_anomaly_model.py before this test."

    def test_known_ports_match_the_real_congestion_dataset(self):
        agent = AnomalyAgent()
        assert "Shanghai" in agent.known_ports
        assert len(agent.known_ports) == 20

    def test_detect_returns_a_real_scored_report(self):
        agent = AnomalyAgent()
        report = agent.detect("Shanghai")

        assert report.affected_region == "Shanghai"
        assert isinstance(report.anomaly_score, float)
        assert isinstance(report.anomaly_detected, bool)
        assert "Shanghai" in report.reason

    def test_unknown_port_raises_rather_than_inventing_a_score(self):
        agent = AnomalyAgent()
        with pytest.raises(ValueError):
            agent.detect("Atlantis")

    def test_reason_names_the_real_deviating_feature(self):
        agent = AnomalyAgent()
        report = agent.detect("Shanghai")
        # The explanation must name one of the five real feature columns,
        # not a generic templated sentence with no connection to the data.
        feature_words = ["congestion index", "avg wait days", "vessels at anchor",
                          "port utilization pct", "berth delay hrs"]
        assert any(w in report.reason for w in feature_words)


class TestAnomaliesApiRoute:
    def _token(self):
        res = client.post(
            "/api/auth/login",
            data={"username": "admin@example.com", "password": "admin"},
        )
        return res.json()["access_token"]

    def test_anomalies_endpoint_returns_all_ports_sorted_worst_first(self):
        token = self._token()
        res = client.get("/api/anomalies", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        anomalies = res.json()["anomalies"]
        assert len(anomalies) == 20
        scores = [a["anomaly_score"] for a in anomalies]
        assert scores == sorted(scores)

    def test_single_port_endpoint(self):
        token = self._token()
        res = client.get("/api/anomalies/Shanghai", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["affected_region"] == "Shanghai"

    def test_unknown_port_is_a_client_error(self):
        token = self._token()
        res = client.get("/api/anomalies/Atlantis", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404
