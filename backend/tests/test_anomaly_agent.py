"""Tests for the Anomaly Detection Agent (Slice 09): real Isolation
Forest scoring over each port's own historical congestion data.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.anomaly.anomaly_agent import AnomalyAgent
from app.agents.ingestion.live_conditions_client import LiveConditionsClient
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


class TestPortSnapshot:
    def test_unknown_port_raises(self):
        agent = AnomalyAgent()
        with pytest.raises(ValueError):
            agent.port_snapshot("Atlantis")

    def test_predict_inputs_match_the_pipeline_s_own_lag_and_rolling_formula(self):
        """merge_congestion_datasets.py builds *_lag1w as shift(1) and
        *_roll4w_mean as a 4-week rolling mean also shift(1)'d -- both
        computed only from weeks strictly before the one being
        described. port_snapshot() must reproduce that exactly, not an
        approximation, since this feeds a real prediction."""
        agent = AnomalyAgent()
        history = agent._history_by_port["Shanghai"]
        snapshot = agent.port_snapshot("Shanghai")

        prior = history.iloc[:-1]
        expected_lag1w = float(prior["congestion_index"].iloc[-1])
        expected_roll4w = float(prior["congestion_index"].tail(4).mean())

        assert snapshot["predict_inputs"]["congestion_index_lag1w"] == pytest.approx(expected_lag1w)
        assert snapshot["predict_inputs"]["congestion_index_roll4w_mean"] == pytest.approx(expected_roll4w)
        assert snapshot["predict_inputs"]["region"] == snapshot["region"]

    def test_trend_is_capped_at_26_weeks_most_recent_first_order(self):
        agent = AnomalyAgent()
        snapshot = agent.port_snapshot("Shanghai")
        assert len(snapshot["trend"]) <= 26
        # Chronological order (oldest to newest), matching the sorted
        # history it's sliced from -- a chart plotting this in order
        # shouldn't need to re-sort it.
        weeks = [t["week_start"] for t in snapshot["trend"]]
        assert weeks == sorted(weeks)

    def test_current_reflects_the_latest_real_row(self):
        agent = AnomalyAgent()
        snapshot = agent.port_snapshot("Shanghai")
        latest_row = agent._latest_by_port["Shanghai"]
        assert snapshot["current"]["congestion_index"] == pytest.approx(float(latest_row["congestion_index"]))
        assert snapshot["week_start"] == str(latest_row["week_start"])


class TestAnomaliesApiRoute:
    def _token(self):
        res = client.post(
            "/api/auth/login",
            data={"username": "admin@example.com", "password": "admin"},
        )
        return res.json()["access_token"]

    def test_anomalies_endpoint_returns_all_ports_sorted_worst_first(self, monkeypatch):
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])
        token = self._token()
        res = client.get("/api/anomalies", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        anomalies = body["anomalies"]
        assert len(anomalies) == 20
        scores = [a["anomaly_score"] for a in anomalies]
        assert scores == sorted(scores)
        # No live reading available (stubbed empty) -- reported honestly
        # as null, not silently dropped or backfilled.
        assert all(a["live_conditions"] is None for a in anomalies)
        assert "live_conditions_status" in body

    def test_anomalies_endpoint_merges_in_real_live_conditions_per_port(self, monkeypatch):
        fake_event = {
            "location": "Shanghai", "event_type": "Slight Sea", "severity": "low",
            "conditions": {"wave_height_m": 1.0, "wind_gusts_kmh": 15},
        }
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [fake_event])
        token = self._token()
        res = client.get("/api/anomalies", headers={"Authorization": f"Bearer {token}"})
        body = res.json()
        shanghai = next(a for a in body["anomalies"] if a["affected_region"] == "Shanghai")
        assert shanghai["live_conditions"]["severity"] == "low"
        assert shanghai["live_conditions"]["conditions"]["wave_height_m"] == 1.0
        # A port with no matching live event stays honestly null.
        other = next(a for a in body["anomalies"] if a["affected_region"] != "Shanghai")
        assert other["live_conditions"] is None

    def test_single_port_endpoint(self):
        token = self._token()
        res = client.get("/api/anomalies/Shanghai", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["affected_region"] == "Shanghai"

    def test_unknown_port_is_a_client_error(self):
        token = self._token()
        res = client.get("/api/anomalies/Atlantis", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404

    def test_port_snapshot_endpoint(self, monkeypatch):
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])
        token = self._token()
        res = client.get("/api/anomalies/Shanghai/snapshot", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert body["port"] == "Shanghai"
        assert "predict_inputs" in body
        assert "trend" in body
        assert body["live_conditions"] is None

    def test_port_snapshot_unknown_port_is_a_client_error(self):
        token = self._token()
        res = client.get("/api/anomalies/Atlantis/snapshot", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404
