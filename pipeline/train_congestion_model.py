"""Trains the congestion classifier on data/features/congestion_features_unified.csv.

Feature selection is explicit and documented, not "use every column" --
several columns in the unified table are outcome-adjacent for at least
one source and would leak if used as features:

- la_lb_visit_2023h2: avg_sog, ping_count, peak_delay_minutes,
  min_distance_to_port, avg_ship_density, avg_port_throughput,
  avg_port_speed, visit_duration_hours are ALL aggregated over the same
  continuous visit as the target (entered_waiting_area = did
  is_in_waiting_area go True at any point in that same visit) -- they
  describe the visit's outcome, not something known before/independent
  of it. Only genuinely static vessel specs (type/length/width/draft/
  cargo) are used from this source.
- port_congestion_2019_2024: congestion_index directly defines
  congestion_flag (thresholded), and vessels_at_anchor/avg_wait_days/
  berth_delay_hrs/port_utilization_pct are definitionally the same
  phenomenon for that same week. Only the *_lag1w / *_roll4w_mean
  versions (built in merge_congestion_datasets.py) are used.

Split is time-based per source (last 20% of each source's own date range
becomes test), not a random shuffle -- this is a forecasting problem, so
evaluating on a random split would be optimistic versus real deployment.

`source` and `entity_type` are kept as categorical features so one model
can adapt to the three different populations/label definitions rather
than pretending they're identical; per-source metrics are reported
alongside the overall ones for exactly that reason.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/train_congestion_model.py
"""

from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, classification_report, roc_auc_score

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_DIR = REPO_ROOT / "data" / "features"
MODEL_PATH = REPO_ROOT / "models" / "saved_models" / "congestion_model.joblib"

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
TARGET_COLUMN = "congestion_flag"


def load_data() -> pd.DataFrame:
    df = pd.read_csv(FEATURES_DIR / "congestion_features_unified.csv", low_memory=False)
    df["window_start"] = pd.to_datetime(df["window_start"], format="mixed", utc=True)
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype("category")
    df = df.dropna(subset=[TARGET_COLUMN])
    df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int)
    return df


def time_based_split(df: pd.DataFrame, test_fraction: float = 0.2) -> tuple:
    """Per-source: last `test_fraction` of that source's own date range is
    the test set. Keeps sources from leaking future-into-past when they
    span very different eras (2012-2018 vs. 2019-2024 vs. 2023H2)."""
    train_parts, test_parts = [], []
    for _, group in df.groupby("source", observed=True):
        group = group.sort_values("window_start")
        cutoff = group["window_start"].quantile(1 - test_fraction)
        train_parts.append(group[group["window_start"] < cutoff])
        test_parts.append(group[group["window_start"] >= cutoff])
    return pd.concat(train_parts), pd.concat(test_parts)


def train_and_evaluate(train: pd.DataFrame, test: pd.DataFrame) -> lgb.LGBMClassifier:
    X_train, y_train = train[FEATURE_COLUMNS], train[TARGET_COLUMN]
    X_test, y_test = test[FEATURE_COLUMNS], test[TARGET_COLUMN]

    model = lgb.LGBMClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        is_unbalance=True,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train, y_train, categorical_feature=CATEGORICAL_FEATURES)

    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    print(f"Overall ROC-AUC: {roc_auc_score(y_test, proba):.3f}")
    print(f"Overall PR-AUC:  {average_precision_score(y_test, proba):.3f}")
    print("\nOverall classification report:")
    print(classification_report(y_test, preds, digits=3))

    print("\nPer-source performance:")
    for source in test["source"].cat.categories:
        mask = test["source"] == source
        if mask.sum() == 0:
            continue
        y_s, p_s = y_test[mask], proba[mask]
        if y_s.nunique() < 2:
            print(f"  {source}: only one class present in test slice, skipping AUC")
            continue
        print(f"  {source}: n={mask.sum()}, ROC-AUC={roc_auc_score(y_s, p_s):.3f}, "
              f"PR-AUC={average_precision_score(y_s, p_s):.3f}, positive_rate={y_s.mean():.3f}")

    print("\nTop 15 feature importances:")
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS).sort_values(ascending=False)
    print(importances.head(15))

    return model


def main() -> None:
    df = load_data()
    train, test = time_based_split(df)
    print(f"Train: {len(train)} rows, Test: {len(test)} rows")

    model = train_and_evaluate(train, test)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\nSaved -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
