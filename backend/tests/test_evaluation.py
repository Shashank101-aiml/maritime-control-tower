"""Tests for the Evaluation harness (Slice 14 / spec sections 29-30):
real persisted training metrics (not printed and lost), and a real
governance-impact comparison computed from recorded execution/approval/
feedback rows, not a simulated benchmark.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance tables exist


class TestModelMetricsEndpoint:
    def test_returns_all_four_known_models(self):
        res = client.get("/api/evaluation/model-metrics")
        assert res.status_code == 200
        body = res.json()
        assert set(body.keys()) == {"congestion", "delay", "fuel", "anomaly"}

    def test_a_trained_models_metrics_include_a_real_baseline_comparison(self):
        # fuel_metrics.json is produced by pipeline/train_fuel_model.py,
        # which is expected to have been run at least once in this repo
        # (models/saved_models/fuel_model.joblib already backs
        # FuelAgent) -- if present, its baseline_mean_mae must be
        # genuinely worse than the trained model's own mae, proving
        # this isn't two copies of the same number.
        res = client.get("/api/evaluation/model-metrics")
        fuel = res.json().get("fuel")
        if fuel is not None:
            assert fuel["baseline_mean_mae"] > fuel["mae"]
            assert "trained_at" in fuel

    def test_a_classifiers_metrics_include_the_no_skill_baseline(self):
        res = client.get("/api/evaluation/model-metrics")
        delay = res.json().get("delay")
        if delay is not None:
            assert delay["pr_auc"] > delay["no_skill_pr_auc"]


class TestGovernanceImpactEndpoint:
    def test_returns_real_computed_counts(self):
        res = client.get("/api/evaluation/governance-impact")
        assert res.status_code == 200
        body = res.json()
        for key in ("total_executions", "gated_for_approval", "approved", "rejected_at_gate", "pending_approval"):
            assert key in body
            assert isinstance(body[key], int)

    def test_gated_for_approval_never_exceeds_total_executions(self):
        # A structural invariant: an approval request always references
        # a real execution, so there can never be more of the former
        # than the latter.
        res = client.get("/api/evaluation/governance-impact").json()
        assert res["gated_for_approval"] <= res["total_executions"]

    def test_rate_fields_are_null_not_a_fabricated_zero_when_nothing_recorded(self):
        res = client.get("/api/evaluation/governance-impact").json()
        if res["total_executions"] == 0:
            assert res["gated_rate"] is None
        if res["feedback_recorded"] == 0:
            assert res["override_rate"] is None
