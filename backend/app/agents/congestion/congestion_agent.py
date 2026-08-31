from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "saved_models" / "congestion_model.joblib"

# Must match pipeline/train_congestion_model.py's FEATURE_COLUMNS exactly --
# duplicated rather than imported since backend/ must be deployable without
# a sibling pipeline/ directory. Keep the two lists in sync by hand.
CATEGORICAL_FEATURES = ["source", "entity_type", "vessel_type", "cargo", "region"]
NUMERIC_FEATURES = [
    "last_lat", "last_lon", "month", "quarter",
    "events_last_4w", "events_last_12w", "duration_last_4w_hours",
    "avg_speed_last_4w_knots", "cumulative_events_to_date", "weeks_since_last_event",
    "lat_grid_cell", "lon_grid_cell",
    "length", "width", "draft",
    "congestion_index_lag1w", "congestion_index_roll4w_mean",
    "avg_wait_days_lag1w", "avg_wait_days_roll4w_mean",
    "vessels_at_anchor_lag1w", "vessels_at_anchor_roll4w_mean",
    "berth_delay_hrs_lag1w", "berth_delay_hrs_roll4w_mean",
    "port_utilization_pct_lag1w", "port_utilization_pct_roll4w_mean",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES


class CongestionAgent:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model = self._load_model(model_path)

    def _load_model(self, model_path: Path):
        if not model_path.exists():
            logger.warning("Congestion model not found at %s", model_path)
            return None
        try:
            import joblib

            return joblib.load(model_path)
        except Exception as exc:
            logger.warning("Could not load congestion model: %s", exc)
            return None

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("Congestion model is not available (not trained/loaded yet).")

        row = {col: features.get(col) for col in FEATURE_COLUMNS}
        frame = pd.DataFrame([row], columns=FEATURE_COLUMNS)
        # An all-None column (unset optional field) defaults to object
        # dtype, which LightGBM rejects -- force numerics to float64 so
        # missing fields become a proper NaN instead.
        frame[NUMERIC_FEATURES] = frame[NUMERIC_FEATURES].astype(float)
        for col in CATEGORICAL_FEATURES:
            frame[col] = frame[col].astype("category")

        proba = float(self.model.predict_proba(frame)[0, 1])
        return {
            "congestion_probability": round(proba, 4),
            "congestion_flag": int(proba >= 0.5),
            "confidence": self._assess_confidence(proba),
        }

    def _assess_confidence(self, proba: float) -> float:
        """Predictions near 0.5 are the model's own uncertain cases;
        predictions near 0 or 1 are ones it's confident about."""
        distance_from_midpoint = abs(proba - 0.5) / 0.5
        return round(0.6 + 0.35 * distance_from_midpoint, 2)


_shared_agent: Optional[CongestionAgent] = None


def get_congestion_agent() -> CongestionAgent:
    global _shared_agent
    if _shared_agent is None:
        _shared_agent = CongestionAgent()
    return _shared_agent
