from pathlib import Path

from app.agents.risk.feature_engineering import FEATURE_COLUMNS, FeatureEngineer
from app.agents.risk.risk_agent import RiskAgent
from app.agents.risk.risk_model import RiskModel


def test_to_vector_matches_feature_columns_order():
    features = FeatureEngineer.combine_features(
        event={"severity": "critical", "source": "AIS", "description": "storm"},
        route={"status": "active", "waypoints": ["a", "b"]},
    )
    vector = FeatureEngineer.to_vector(features)
    assert len(vector) == len(FEATURE_COLUMNS)
    assert vector[FEATURE_COLUMNS.index("event_severity_score")] == 4.0
    assert vector[FEATURE_COLUMNS.index("route_waypoint_count")] == 2.0


def test_to_vector_defaults_missing_features_to_zero():
    vector = FeatureEngineer.to_vector({})
    assert vector == [0.0] * len(FEATURE_COLUMNS)


def test_risk_model_falls_back_to_rule_based_when_no_model_file():
    model = RiskModel(model_path=Path("does/not/exist.joblib"))
    assert model.is_ml_backed is False

    result = model.predict(event={"severity": "critical"})
    assert result["scoring_method"] == "rule_based"
    assert 0 <= result["score"] <= 100


def test_risk_model_uses_trained_model_when_present():
    trained_model_path = Path(__file__).resolve().parents[3] / "models" / "saved_models" / "risk_model.joblib"
    if not trained_model_path.exists():
        return  # training pipeline hasn't been run in this environment; nothing to assert

    model = RiskModel(model_path=trained_model_path)
    assert model.is_ml_backed is True

    result = model.predict(event={"severity": "critical"})
    assert result["scoring_method"] == "ml"


def test_confidence_penalized_for_rule_based_fallback():
    agent = RiskAgent()
    ml_confidence = agent.assess_confidence(score=90, scoring_method="ml")
    rule_based_confidence = agent.assess_confidence(score=90, scoring_method="rule_based")
    assert rule_based_confidence < ml_confidence
