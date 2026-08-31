"""Trains the risk-scoring ML model used by backend/app/agents/risk/risk_model.py.

There's no historical maritime incident dataset yet, so this bootstraps one:
it samples random event/route/risk combinations across the same categories
the agents already reason about, labels each with the existing rule-based
RiskScorer (plus a little noise, so the model learns a generalizable mapping
instead of just memorizing the rule), and trains a regressor on that.

Swap `generate_dataset()` for a loader over real historical data later and
the rest of the pipeline (features -> train -> evaluate -> save) stays the same.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/pipeline.py
"""

import random
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.agents.risk.feature_engineering import FEATURE_COLUMNS, FeatureEngineer  # noqa: E402
from app.agents.risk.scoring import RiskScorer  # noqa: E402

DATASET_PATH = REPO_ROOT / "data" / "processed" / "risk_features.csv"
MODEL_PATH = REPO_ROOT / "models" / "saved_models" / "risk_model.joblib"

EVENT_SEVERITIES = ["critical", "high", "warning", "medium", "low", "info"]
ROUTE_STATUSES = ["pending", "planned", "in_progress", "active", "open", "failed", "completed", "closed"]
RISK_LIKELIHOODS = ["very high", "high", "medium", "low", "very low"]
RISK_IMPACTS = ["critical", "high", "medium", "low", "minor"]
LABEL_NOISE_STD = 4.0


def _sample_case(rng: random.Random) -> tuple:
    event = {
        "severity": rng.choice(EVENT_SEVERITIES),
        "source": rng.choice(["AIS", "weather-feed", None]),
        "description": rng.choice(["Observed hazard in transit corridor", None]),
    }
    route = {
        "status": rng.choice(ROUTE_STATUSES),
        "origin": rng.choice(["Port of Singapore", None]),
        "destination": rng.choice(["Port of Rotterdam", None]),
        "waypoints": [f"WP-{i}" for i in range(rng.randint(0, 10))],
        "notes": rng.choice(["Reroute pending confirmation", None]),
    }
    risk = {
        "likelihood": rng.choice(RISK_LIKELIHOODS),
        "impact": rng.choice(RISK_IMPACTS),
        "status": rng.choice(ROUTE_STATUSES),
        "is_active": rng.choice([True, False]),
        "mitigation_plan": rng.choice(["Divert 120nm south", None]),
    }
    return event, route, risk


def generate_dataset(n_samples: int = 5000, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    noise_rng = np.random.default_rng(seed)

    rows = []
    for _ in range(n_samples):
        event, route, risk = _sample_case(rng)

        features = FeatureEngineer.combine_features(event=event, route=route, risk=risk)
        vector = FeatureEngineer.to_vector(features)

        label = RiskScorer.evaluate(event=event, route=route, risk=risk)["score"]
        label = float(np.clip(label + noise_rng.normal(0, LABEL_NOISE_STD), 0, 100))

        rows.append(vector + [label])

    return pd.DataFrame(rows, columns=FEATURE_COLUMNS + ["risk_score"])


def train_model(df: pd.DataFrame) -> tuple:
    X = df[FEATURE_COLUMNS]
    y = df["risk_score"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    metrics = {
        "mae": mean_absolute_error(y_test, predictions),
        "r2": r2_score(y_test, predictions),
    }
    return model, metrics


def main() -> None:
    print(f"Generating synthetic training data -> {DATASET_PATH}")
    df = generate_dataset()
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATASET_PATH, index=False)

    print("Training risk model...")
    model, metrics = train_model(df)
    print(f"Test MAE: {metrics['mae']:.2f}  |  Test R2: {metrics['r2']:.3f}")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Saved trained model -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
