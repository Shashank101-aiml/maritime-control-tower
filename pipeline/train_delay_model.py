"""Trains the shipment-delay classifier on data/features/delay_features.csv.

Two things discovered only while building this training script, not
caught earlier, worth being upfront about:

1. `order_date` is IDENTICAL across all 9,215 rows (2013-05-26). There is
   no temporal dimension in this dataset at all, despite the column
   names suggesting one. That makes order_month/order_day_of_week
   constant (dropped here -- zero variance, pure noise) and means
   `backlog_vs_capacity` is really "this plant's total order count
   across the whole dataset vs. its daily capacity," not a rolling
   weekly congestion signal as originally described when the feature
   was built. Still a legitimate static capacity-pressure proxy, just
   not a temporal one.
2. No time-based split is possible without a time axis, so this uses a
   stratified random split instead (stratify=is_late) to keep the rare
   positive class represented in both train and test.

`is_late` is severely imbalanced: 192/9,215 positive (2.08%). A held-out
test set at a 75/25 split has roughly 48 positive examples -- real, but
thin enough that the reported metrics have real sampling noise. Reported
plainly rather than smoothed over.

`product_id` (772 distinct values across 9,215 rows, ~12 rows/product)
is excluded as a feature -- too sparse to generalize from, high risk of
just memorizing per-product noise at this sample size.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/train_delay_model.py
"""

from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd
from sklearn.metrics import average_precision_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_DIR = REPO_ROOT / "data" / "features"
MODEL_PATH = REPO_ROOT / "models" / "saved_models" / "delay_model.joblib"

CATEGORICAL_FEATURES = ["origin_port", "carrier", "service_level", "customer", "plant_code", "destination_port"]
NUMERIC_FEATURES = [
    "tpt", "unit_quantity", "weight", "freight_rate", "freight_min_cost",
    "wh_cost_per_unit", "wh_daily_capacity", "plant_week_order_count",
    "backlog_vs_capacity", "is_vmi_customer_anywhere",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_COLUMN = "is_late"


def load_data() -> pd.DataFrame:
    df = pd.read_csv(FEATURES_DIR / "delay_features.csv")
    df["is_vmi_customer_anywhere"] = df["is_vmi_customer_anywhere"].astype(int)
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype("category")
    return df


def train_and_evaluate(df: pd.DataFrame) -> lgb.LGBMClassifier:
    X, y = df[FEATURE_COLUMNS], df[TARGET_COLUMN]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    print(f"Train: {len(X_train)} rows ({y_train.sum()} positive), "
          f"Test: {len(X_test)} rows ({y_test.sum()} positive)")

    model = lgb.LGBMClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        is_unbalance=True,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train, y_train, categorical_feature=CATEGORICAL_FEATURES)

    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    print(f"\nROC-AUC: {roc_auc_score(y_test, proba):.3f}")
    print(f"PR-AUC:  {average_precision_score(y_test, proba):.3f}  "
          f"(baseline/no-skill PR-AUC = positive rate = {y_test.mean():.3f})")
    print("\nClassification report:")
    print(classification_report(y_test, preds, digits=3))

    print("Feature importances:")
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS).sort_values(ascending=False)
    print(importances)

    return model


def main() -> None:
    df = load_data()
    model = train_and_evaluate(df)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\nSaved -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
