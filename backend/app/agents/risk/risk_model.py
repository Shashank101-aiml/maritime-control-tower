from pathlib import Path
from typing import Any, Dict, Optional

from app.agents.risk.feature_engineering import FEATURE_COLUMNS, FeatureEngineer
from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "saved_models" / "risk_model.joblib"


class RiskModel:
    """Predicts a 0-100 risk score from engineered event/route/risk features.

    Tries the trained ML model (models/saved_models/risk_model.joblib,
    produced by pipeline/pipeline.py) first. If it hasn't been trained yet,
    or fails to load, falls back to a hand-weighted linear combination of
    the same features so the agent pipeline never hard-depends on a model
    file being present.
    """

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        default_weights: Dict[str, float] = {
            "event_severity_score": 0.30,
            "route_status_score": 0.20,
            "risk_likelihood_score": 0.20,
            "risk_impact_score": 0.20,
            "route_waypoint_count": 0.05,
            "event_has_description": 0.02,
            "event_source_provided": 0.02,
            "route_has_origin": 0.01,
            "route_has_destination": 0.01,
            "route_notes_provided": 0.01,
            "risk_has_mitigation_plan": 0.03,
            "risk_is_active": 0.05,
        }
        self.weights = {**default_weights, **(weights or {})}
        self.model = self._load_model(model_path)

    def _load_model(self, model_path: Path):
        if not model_path.exists():
            return None
        try:
            import joblib

            return joblib.load(model_path)
        except Exception as exc:  # missing joblib, corrupt file, version mismatch, etc.
            logger.warning("Could not load trained risk model from %s: %s", model_path, exc)
            return None

    @property
    def is_ml_backed(self) -> bool:
        return self.model is not None

    def predict(
        self,
        event: Dict[str, Any],
        route: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        features = FeatureEngineer.combine_features(event=event, route=route, risk=risk)

        if self.model is not None:
            try:
                score = self._predict_ml(features)
                method = "ml"
            except Exception as exc:
                logger.warning("ML risk prediction failed, using rule-based fallback: %s", exc)
                score = self._predict_weighted(features)
                method = "rule_based"
        else:
            score = self._predict_weighted(features)
            method = "rule_based"

        return {
            "score": score,
            "risk_level": self._risk_level(score),
            "likelihood": self._likelihood(score),
            "impact": self._impact(score),
            "scoring_method": method,
            "features": features,
        }

    def _predict_ml(self, features: Dict[str, Any]) -> int:
        import pandas as pd

        vector = FeatureEngineer.to_vector(features)
        row = pd.DataFrame([vector], columns=FEATURE_COLUMNS)
        raw_score = float(self.model.predict(row)[0])
        return int(round(max(0.0, min(100.0, raw_score))))

    def _predict_weighted(self, features: Dict[str, Any]) -> int:
        total = 0.0
        for name, value in features.items():
            weight = self.weights.get(name)
            if weight is None:
                continue
            if isinstance(value, bool):
                value = 1 if value else 0
            if isinstance(value, (int, float)):
                total += float(value) * weight

        return int(round(max(0.0, min(100.0, total * 10.0))))

    def _risk_level(self, score: int) -> str:
        if score >= 75:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    def _likelihood(self, score: int) -> str:
        if score >= 70:
            return "high"
        if score >= 45:
            return "medium"
        return "low"

    def _impact(self, score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 55:
            return "high"
        if score >= 30:
            return "medium"
        return "low"


_shared_risk_model: Optional[RiskModel] = None


def get_risk_model() -> RiskModel:
    """Module-level singleton so the trained model is loaded from disk once
    per process, not on every single agent invocation."""
    global _shared_risk_model
    if _shared_risk_model is None:
        _shared_risk_model = RiskModel()
    return _shared_risk_model
