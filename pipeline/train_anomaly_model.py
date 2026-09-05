"""Trains the anomaly detector on data/cleaned/port_congestion.csv.

Unsupervised (Isolation Forest), per spec section 8's guidance to
start with Isolation Forest rather than reaching for a supervised model
with no labeled "anomaly" ground truth to train against -- there is no
anomaly_flag column in this data, nor should one be invented.

Features are exactly the five real per-port-week congestion columns
already used elsewhere in this repo (the digital twin's congestion
percentile, the congestion classifier's lag/rolling features derive
from these same source columns): congestion_index, avg_wait_days,
vessels_at_anchor, port_utilization_pct, berth_delay_hrs. No AIS/
loitering features yet -- those live in separate, differently-shaped
CSVs (per-voyage, not per-port-week) and would need their own
aggregation step; congestion alone is real, available, and already
the primary signal spec section 8 names for this agent.

`contamination=0.05` is Isolation Forest's own standard default framing
(scikit-learn's historical default), not a value tuned to this data --
it's an assumption about how much of history is "expected" to be
unusual, stated plainly rather than left implicit.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/train_anomaly_model.py
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

from evaluation_utils import save_metrics

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = REPO_ROOT / "data" / "cleaned" / "port_congestion.csv"
MODEL_PATH = REPO_ROOT / "models" / "saved_models" / "anomaly_model.joblib"

FEATURE_COLUMNS = [
    "congestion_index",
    "avg_wait_days",
    "vessels_at_anchor",
    "port_utilization_pct",
    "berth_delay_hrs",
]

CONTAMINATION = 0.05


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    return df.dropna(subset=FEATURE_COLUMNS)


def main() -> None:
    df = load_data()
    X = df[FEATURE_COLUMNS]

    model = IsolationForest(
        n_estimators=200,
        contamination=CONTAMINATION,
        random_state=42,
    )
    model.fit(X)

    scores = model.decision_function(X)
    flags = model.predict(X)
    print(f"Trained on {len(df)} real port-weeks across {df['port'].nunique()} ports.")
    print(f"Flagged as anomalous: {(flags == -1).sum()} ({(flags == -1).mean():.1%})")
    print(f"Score range: {scores.min():.3f} to {scores.max():.3f} (lower = more anomalous)")

    print("\nMost anomalous real port-weeks:")
    df = df.assign(_score=scores)
    print(
        df.nsmallest(10, "_score")[["port", "week_start", "congestion_index", "avg_wait_days", "_score"]]
        .to_string(index=False)
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\nSaved -> {MODEL_PATH}")

    metrics = {
        "n_samples": int(len(df)),
        "n_ports": int(df["port"].nunique()),
        "contamination": CONTAMINATION,
        "flagged_count": int((flags == -1).sum()),
        "flagged_rate": round(float((flags == -1).mean()), 4),
        "score_min": round(float(scores.min()), 4),
        "score_max": round(float(scores.max()), 4),
    }
    metrics_path = save_metrics("anomaly", metrics)
    print(f"Metrics saved -> {metrics_path}")


if __name__ == "__main__":
    main()
