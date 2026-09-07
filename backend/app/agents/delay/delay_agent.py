from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "saved_models" / "delay_model.joblib"
FEATURES_PATH = Path(__file__).resolve().parents[4] / "data" / "features" / "delay_features.csv"
PLANT_PORTS_PATH = Path(__file__).resolve().parents[4] / "data" / "cleaned" / "supply_chain" / "plant_ports.csv"

# Must match pipeline/train_delay_model.py's FEATURE_COLUMNS exactly --
# duplicated rather than imported, see congestion_agent.py for why.
CATEGORICAL_FEATURES = ["origin_port", "carrier", "service_level", "customer", "plant_code", "destination_port"]
NUMERIC_FEATURES = [
    "tpt", "unit_quantity", "weight", "freight_rate", "freight_min_cost",
    "wh_cost_per_unit", "wh_daily_capacity", "plant_week_order_count",
    "backlog_vs_capacity", "is_vmi_customer_anywhere",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# This is the same real training data the model was fit on
# (data/features/delay_features.csv, built from the DataCo-style
# anonymized supply-chain export in data/cleaned/supply_chain/) --
# not a separate or invented source. Its categorical universe is real
# but small (3 origin ports, 1 destination port, 3 carriers, 7 plants):
# every "PORT0x"/"PLANT0x" code here is a synthetic identifier from
# this dataset, unrelated to the real named maritime ports (Shanghai,
# Singapore, ...) the congestion/anomaly module scores. There is no
# shared identity between the two -- pretending PORT09 corresponds to
# a real port would be fabricating a connection the data doesn't have.
DELAY_OVERVIEW_COLUMNS = [
    "origin_port", "destination_port", "carrier", "service_level", "customer", "plant_code",
    "tpt", "unit_quantity", "weight", "freight_rate", "freight_min_cost",
    "wh_cost_per_unit", "wh_daily_capacity", "plant_week_order_count",
    "backlog_vs_capacity", "is_vmi_customer_anywhere", "is_late",
]


class DelayAgent:
    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        features_path: Path = FEATURES_PATH,
        plant_ports_path: Path = PLANT_PORTS_PATH,
    ) -> None:
        self.model = self._load_model(model_path)
        self._orders = self._load_features(features_path)
        self._plant_ports = self._load_plant_ports(plant_ports_path)

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

    def _load_features(self, features_path: Path) -> Optional[pd.DataFrame]:
        try:
            df = pd.read_csv(features_path, usecols=DELAY_OVERVIEW_COLUMNS)
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Delay training data not found/usable at %s: %s", features_path, exc)
            return None
        df["is_vmi_customer_anywhere"] = df["is_vmi_customer_anywhere"].astype(bool)
        return df

    def _load_plant_ports(self, plant_ports_path: Path) -> Dict[str, List[str]]:
        try:
            df = pd.read_csv(plant_ports_path)
        except FileNotFoundError:
            logger.warning("Plant/port mapping not found at %s", plant_ports_path)
            return {}
        mapping: Dict[str, List[str]] = {}
        for plant, group in df.groupby("plant_code"):
            mapping[plant] = sorted(group["port"].unique().tolist())
        return mapping

    @property
    def is_available(self) -> bool:
        return self.model is not None

    @property
    def has_reference_data(self) -> bool:
        return self._orders is not None

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

    def overview(self) -> Dict[str, Any]:
        """Real historical shape of the training data: overall late
        rate, a per-category late-rate breakdown, every real value each
        categorical field actually takes (for a dropdown that can't be
        set to a combination the model never saw), and the real plant
        -> port associations from data/cleaned/supply_chain/
        plant_ports.csv -- not the same ports the congestion module
        scores (see the module docstring), but a real relationship
        within this dataset that the old free-text form ignored.
        """
        if self._orders is None:
            raise RuntimeError("Delay training data is not available.")

        df = self._orders
        overall_late_rate = float(df["is_late"].mean())

        breakdown_columns = ["carrier", "plant_code", "service_level", "origin_port"]
        breakdown = {
            col: self._breakdown_by(df, col) for col in breakdown_columns
        }

        known_values = {
            col: sorted(df[col].dropna().unique().tolist())
            for col in ["origin_port", "destination_port", "carrier", "plant_code", "service_level", "customer"]
        }

        # Dataset-wide medians for the numeric fields the old form left
        # blank -- shown as real placeholder hints ("e.g. 0.55") rather
        # than an invented example number, so a field left empty still
        # gives a sense of scale.
        typical_columns = [
            "tpt", "unit_quantity", "weight", "freight_rate", "freight_min_cost",
            "wh_cost_per_unit", "wh_daily_capacity", "plant_week_order_count", "backlog_vs_capacity",
        ]
        typical = {col: _clean_number(df[col].median()) for col in typical_columns}

        return {
            "orders": int(len(df)),
            "overall_late_rate": round(overall_late_rate, 4),
            "breakdown": breakdown,
            "typical": typical,
            "known_values": known_values,
            "plant_ports": self._plant_ports,
        }

    @staticmethod
    def _breakdown_by(df: "pd.DataFrame", column: str) -> List[Dict[str, Any]]:
        grouped = df.groupby(column)["is_late"].agg(["mean", "count"]).reset_index()
        grouped = grouped.sort_values("mean", ascending=False)
        return [
            {"value": row[column], "orders": int(row["count"]), "late_rate": round(float(row["mean"]), 4)}
            for _, row in grouped.iterrows()
        ]

    def plant_profile(self, plant_code: str) -> Dict[str, Any]:
        """A real representative order for this plant -- median of every
        real numeric feature and the most common real category, computed
        from this plant's own historical rows, not invented defaults.
        Feeds the "use this plant's real profile" prefill so a manual
        prediction can actually supply the numeric features
        (freight_rate, wh_daily_capacity, ...) the model was trained on
        but the old form never collected at all.
        """
        if self._orders is None:
            raise RuntimeError("Delay training data is not available.")

        rows = self._orders[self._orders["plant_code"] == plant_code]
        if rows.empty:
            raise ValueError(f"{plant_code!r} has no orders in the training data.")

        def mode(col: str) -> Any:
            values = rows[col].mode()
            return values.iloc[0] if len(values) else None

        numeric_cols = [
            "tpt", "unit_quantity", "weight", "freight_rate", "freight_min_cost",
            "wh_cost_per_unit", "wh_daily_capacity", "plant_week_order_count", "backlog_vs_capacity",
        ]
        profile = {col: _clean_number(rows[col].median()) for col in numeric_cols}
        profile["is_vmi_customer_anywhere"] = bool(rows["is_vmi_customer_anywhere"].mode().iloc[0])
        profile["origin_port"] = mode("origin_port")
        profile["destination_port"] = mode("destination_port")
        profile["carrier"] = mode("carrier")
        profile["service_level"] = mode("service_level")
        profile["customer"] = mode("customer")

        return {
            "plant_code": plant_code,
            "orders": int(len(rows)),
            "late_rate": round(float(rows["is_late"].mean()), 4),
            "real_ports": self._plant_ports.get(plant_code, []),
            "profile": profile,
        }


def _clean_number(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else round(f, 4)


_shared_agent: Optional[DelayAgent] = None


def get_delay_agent() -> DelayAgent:
    global _shared_agent
    if _shared_agent is None:
        _shared_agent = DelayAgent()
    return _shared_agent
