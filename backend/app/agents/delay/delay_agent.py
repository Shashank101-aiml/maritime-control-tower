from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "saved_models" / "delay_model.joblib"

# Must match pipeline/train_delay_model.py's FEATURE_COLUMNS exactly --
# duplicated rather than imported, see congestion_agent.py for why.
CATEGORICAL_FEATURES = ["origin_port", "carrier", "service_level", "customer", "plant_code", "destination_port"]
NUMERIC_FEATURES = [
    "tpt", "unit_quantity", "weight", "freight_rate", "freight_min_cost",
    "wh_cost_per_unit", "wh_daily_capacity", "plant_week_order_count",
    "backlog_vs_capacity", "is_vmi_customer_anywhere",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES


class DelayAgent:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model = self._load_model(model_path)

    def _load_model(self, model_path: Path):
        if not model_path.exists():
            logger.warning("Delay model not found at %s", model_path)
            return None
        try:
            import joblib

            return joblib.load(model_path)
        except Exception as exc:
            logger.warning("Could not load delay model: %s", exc)
            return None

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("Delay model is not available (not trained/loaded yet).")

        row = {col: features.get(col) for col in FEATURE_COLUMNS}
        if "is_vmi_customer_anywhere" in row and row["is_vmi_customer_anywhere"] is not None:
            row["is_vmi_customer_anywhere"] = int(bool(row["is_vmi_customer_anywhere"]))
        frame = pd.DataFrame([row], columns=FEATURE_COLUMNS)
        # An all-None column (unset optional field) defaults to object
        # dtype, which LightGBM rejects -- force numerics to float64 so
        # missing fields become a proper NaN instead.
        frame[NUMERIC_FEATURES] = frame[NUMERIC_FEATURES].astype(float)
        for col in CATEGORICAL_FEATURES:
            frame[col] = frame[col].astype("category")

        proba = float(self.model.predict_proba(frame)[0, 1])
        return {
            "late_probability": round(proba, 4),
            "is_late_flag": int(proba >= 0.5),
            "confidence": self._assess_confidence(proba),
        }

    def _assess_confidence(self, proba: float) -> float:
        distance_from_midpoint = abs(proba - 0.5) / 0.5
        return round(0.6 + 0.35 * distance_from_midpoint, 2)


_shared_agent: Optional[DelayAgent] = None


def get_delay_agent() -> DelayAgent:
    global _shared_agent
    if _shared_agent is None:
        _shared_agent = DelayAgent()
    return _shared_agent
