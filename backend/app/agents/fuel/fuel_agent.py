from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "saved_models" / "fuel_model.joblib"

# Must match pipeline/train_fuel_model.py's FEATURE_COLUMNS exactly --
# duplicated rather than imported, see congestion_agent.py for why.
CATEGORICAL_FEATURES = ["ship_type", "route_id", "fuel_type", "weather_conditions"]
NUMERIC_FEATURES = ["distance", "month_num"]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# Same illustrative reference prices as
# pipeline/build_fuel_efficiency_features.py -- see that file for why
# these are liters, not tons, and why they're fixed reference values, not
# a live feed.
FUEL_PRICE_USD_PER_LITER = {"HFO": 0.55, "Diesel": 0.80}

# The only categories the model was actually trained on -- used purely to
# flag when a request extrapolates beyond the training data, not to
# validate/reject input.
KNOWN_CATEGORIES = {
    "ship_type": {"Oil Service Boat", "Fishing Trawler", "Surfer Boat", "Tanker Ship"},
    "route_id": {"Warri-Bonny", "Port Harcourt-Lagos", "Bonny-Lagos", "Lagos-Warri"},
    "fuel_type": {"HFO", "Diesel"},
    "weather_conditions": {"Stormy", "Moderate", "Calm"},
}


class FuelAgent:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model = self._load_model(model_path)

    def _load_model(self, model_path: Path):
        if not model_path.exists():
            logger.warning("Fuel model not found at %s", model_path)
            return None
        try:
            import joblib

            return joblib.load(model_path)
        except Exception as exc:
            logger.warning("Could not load fuel model: %s", exc)
            return None

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("Fuel model is not available (not trained/loaded yet).")

        row = {col: features.get(col) for col in FEATURE_COLUMNS}
        frame = pd.DataFrame([row], columns=FEATURE_COLUMNS)
        frame[NUMERIC_FEATURES] = frame[NUMERIC_FEATURES].astype(float)
        for col in CATEGORICAL_FEATURES:
            frame[col] = frame[col].astype("category")

        predicted_fuel = float(self.model.predict(frame)[0])
        fuel_type = features.get("fuel_type")
        price_per_liter = FUEL_PRICE_USD_PER_LITER.get(fuel_type)
        estimated_cost_usd = predicted_fuel * price_per_liter if price_per_liter else None

        return {
            "predicted_fuel_consumption": round(predicted_fuel, 2),
            "estimated_cost_usd": round(estimated_cost_usd, 2) if estimated_cost_usd is not None else None,
            "confidence": self._assess_confidence(row),
        }

    def _assess_confidence(self, row: Dict[str, Any]) -> float:
        """No ground truth at inference time, so confidence here reflects
        whether the request is within the categories the model actually
        saw during training rather than an extrapolation."""
        known = sum(
            1 for col, allowed in KNOWN_CATEGORIES.items()
            if row.get(col) in allowed
        )
        return round(0.5 + 0.4 * (known / len(KNOWN_CATEGORIES)), 2)


_shared_agent: Optional[FuelAgent] = None


def get_fuel_agent() -> FuelAgent:
    global _shared_agent
    if _shared_agent is None:
        _shared_agent = FuelAgent()
    return _shared_agent
