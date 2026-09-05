"""Trains the fuel-consumption regressor on
data/features/fuel_efficiency_features.csv.

Target: fuel_consumption -- "how much fuel will this trip use" is the
actionable prediction; cost/CO2/savings are all straightforward
downstream conversions of it (see build_fuel_efficiency_features.py),
not separate things to predict.

Feature selection excludes everything derived from or concurrent with
fuel_consumption itself: fuel_per_distance and co2_per_distance are
literally fuel_consumption divided by distance; co2_emissions tracks
fuel burned almost one-to-one (same combustion event); estimated_cost_usd
and the benchmark_*/cost_savings_potential_usd columns are downstream
arithmetic on fuel_consumption; engine_efficiency describes the same
trip's engine performance concurrently, not something known beforehand.
Only genuinely pre-trip-known info is used: ship_type, route_id,
fuel_type, weather_conditions, distance, month. ship_id is excluded too
-- 120 ships over 1,440 rows is ~12 rows/ship, too sparse to learn
per-vessel effects from; ship_type already captures the vessel class.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/train_fuel_model.py
"""

from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split

from evaluation_utils import save_metrics

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_DIR = REPO_ROOT / "data" / "features"
MODEL_PATH = REPO_ROOT / "models" / "saved_models" / "fuel_model.joblib"

CATEGORICAL_FEATURES = ["ship_type", "route_id", "fuel_type", "weather_conditions"]
NUMERIC_FEATURES = ["distance", "month_num"]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_COLUMN = "fuel_consumption"


def load_data() -> pd.DataFrame:
    df = pd.read_csv(FEATURES_DIR / "fuel_efficiency_features.csv")
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype("category")
    return df


def train_and_evaluate(df: pd.DataFrame) -> "tuple[lgb.LGBMRegressor, dict]":
    X, y = df[FEATURE_COLUMNS], df[TARGET_COLUMN]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"Train: {len(X_train)} rows, Test: {len(X_test)} rows")

    model = lgb.LGBMRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train, y_train, categorical_feature=CATEGORICAL_FEATURES)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = root_mean_squared_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    # Spec section 30's baseline: a model that always predicts the
    # training mean, regardless of input -- R2 is already defined
    # relative to exactly this baseline, but its MAE is reported
    # explicitly too since that's the unit the headline MAE above is in.
    baseline_preds = [y_train.mean()] * len(y_test)
    baseline_mae = mean_absolute_error(y_test, baseline_preds)

    print(f"\nMAE:  {mae:.1f}  (mean fuel_consumption = {y_test.mean():.1f}, "
          f"MAE/mean = {mae / y_test.mean():.1%})")
    print(f"RMSE: {rmse:.1f}")
    print(f"R2:   {r2:.3f}")
    print(f"Baseline (always predict the mean) MAE: {baseline_mae:.1f}")

    print("\nFeature importances:")
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS).sort_values(ascending=False)
    print(importances)

    metrics = {
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "r2": round(float(r2), 4),
        "baseline_mean_mae": round(float(baseline_mae), 2),
    }
    return model, metrics


def main() -> None:
    df = load_data()
    model, metrics = train_and_evaluate(df)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\nSaved -> {MODEL_PATH}")

    metrics_path = save_metrics("fuel", metrics)
    print(f"Metrics saved -> {metrics_path}")


if __name__ == "__main__":
    main()
