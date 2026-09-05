"""Real anomaly detection over per-port congestion history (spec
section 8). Isolation Forest (pipeline/train_anomaly_model.py), scored
against each port's own real weekly history in data/cleaned/
port_congestion.csv -- the same source the digital twin's congestion
percentile and the congestion classifier already use.

Unsupervised by necessity: there is no labeled "this was an anomaly"
column in this data, so a supervised model would need an invented
target. Isolation Forest needs no such label -- it's spec section 8's
own suggested starting point for exactly this reason.
"""

from pathlib import Path
from typing import Dict, List, Optional

import joblib
import pandas as pd

from app.core.logging import get_logger
from app.schemas.agent_io import AnomalyReport

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "saved_models" / "anomaly_model.joblib"
DATA_PATH = Path(__file__).resolve().parents[4] / "data" / "cleaned" / "port_congestion.csv"

FEATURE_COLUMNS = [
    "congestion_index",
    "avg_wait_days",
    "vessels_at_anchor",
    "port_utilization_pct",
    "berth_delay_hrs",
]


class AnomalyAgent:
    def __init__(self, model_path: Path = MODEL_PATH, data_path: Path = DATA_PATH) -> None:
        self.model = self._load_model(model_path)
        self._latest_by_port, self._history_by_port = self._load_data(data_path)

    def _load_model(self, model_path: Path):
        if not model_path.exists():
            logger.warning("Anomaly model not found at %s", model_path)
            return None
        try:
            return joblib.load(model_path)
        except Exception as exc:
            logger.warning("Could not load anomaly model: %s", exc)
            return None

    def _load_data(self, data_path: Path):
        try:
            df = pd.read_csv(data_path)
        except FileNotFoundError:
            logger.warning("Port congestion data not found at %s", data_path)
            return {}, {}
        df = df.dropna(subset=FEATURE_COLUMNS)

        latest: Dict[str, "pd.Series"] = {}
        history: Dict[str, "pd.DataFrame"] = {}
        for port, group in df.groupby("port"):
            group = group.sort_values("week_start")
            latest[port] = group.iloc[-1]
            history[port] = group
        return latest, history

    @property
    def is_available(self) -> bool:
        return self.model is not None

    @property
    def known_ports(self) -> List[str]:
        return list(self._latest_by_port.keys())

    def detect(self, port: str) -> AnomalyReport:
        if self.model is None:
            raise RuntimeError("Anomaly model is not available (not trained/loaded yet).")
        if port not in self._latest_by_port:
            raise ValueError(f"{port!r} has no congestion history to score.")

        row = self._latest_by_port[port]
        frame = row[FEATURE_COLUMNS].to_frame().T.astype(float)

        score = float(self.model.decision_function(frame)[0])
        flagged = bool(self.model.predict(frame)[0] == -1)

        return AnomalyReport(
            anomaly_detected=flagged,
            anomaly_score=round(score, 4),
            affected_region=port,
            reason=self._explain(port, row),
        )

    def _explain(self, port: str, row: "pd.Series") -> str:
        """Which real feature deviates furthest (in standard deviations)
        from this port's own historical mean -- a genuinely computed
        explanation, not a canned sentence picked by score threshold."""
        history = self._history_by_port[port]
        deviations = {}
        for col in FEATURE_COLUMNS:
            mean = history[col].mean()
            std = history[col].std()
            if not std or pd.isna(std):
                continue
            deviations[col] = abs(row[col] - mean) / std

        if not deviations:
            return f"{port}: latest congestion snapshot (week of {row['week_start']}) scored against its own history."

        worst = max(deviations, key=deviations.get)
        return (
            f"{port}'s {worst.replace('_', ' ')} ({row[worst]:.1f}) is {deviations[worst]:.1f} standard "
            f"deviations from its own historical mean (week of {row['week_start']})."
        )


_shared_agent: Optional[AnomalyAgent] = None


def get_anomaly_agent() -> AnomalyAgent:
    global _shared_agent
    if _shared_agent is None:
        _shared_agent = AnomalyAgent()
    return _shared_agent
