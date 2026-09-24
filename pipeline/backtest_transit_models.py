"""Does any model predict a container's ocean transit better than its lane's
own history? Tested honestly, out of time, and the answer is what gets saved.

This replaces the old shipment-delay classifier, which was trained on an
anonymized supply-chain sample and reported an implausible 0.996 ROC-AUC.
Here the data is the real container journeys (see build_transit_journeys.py)
and the test is a rolling, expanding-window, out-of-time backtest: each fold
trains only on journeys loaded *before* the fold and is scored on journeys
loaded *after* it, so nothing from the future leaks into a prediction.

Two questions, each against its natural baseline:
  1. Transit days.  Baseline: the lane's median from training data.
                    Model: LightGBM on the lane deviation, using distance,
                    season and real weekly port congestion at loading.
  2. Delayed?       "Took at least N days longer than the lane's median."
                    Baseline: the lane's own historical delay rate.
                    Models: LightGBM and logistic regression on the same features.

A model is only worth serving if it beats its baseline across folds. The
saved metrics record what actually happened, including when nothing did.

Run from the repo root:
    python pipeline/backtest_transit_models.py
"""

import warnings
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, roc_auc_score

from evaluation_utils import save_metrics

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parents[1]
JOURNEYS = REPO_ROOT / "data" / "features" / "transit_journeys.csv"
CONGESTION = REPO_ROOT / "data" / "cleaned" / "port_congestion.csv"

FOLD_START_QUANTILES = (0.50, 0.65, 0.80)
DELAY_THRESHOLDS = (7, 10)
MIN_LANE_JOURNEYS = 15
FEATURES = ["distance_nm", "month", "origin_cong", "origin_cong_4w", "dest_cong", "dest_cong_4w"]

# Public port-area coordinates for the ports the journeys touch (lat, lon).
COORDS = {
    "Yantian": (22.57, 114.28), "Shanghai": (31.23, 121.47), "Ningbo": (29.87, 121.55),
    "Vung Tau": (10.35, 107.07), "Cai Mep": (10.53, 107.03), "Ho Chi Minh City": (10.77, 106.79),
    "Chattogram": (22.31, 91.80), "Tianjin Xingang": (39.00, 117.75), "Xiamen": (24.45, 118.07),
    "Nansha": (22.75, 113.61), "Long Beach": (33.75, -118.19), "Los Angeles": (33.73, -118.26),
    "Houston": (29.73, -95.27), "Oakland": (37.80, -122.32),
}
# Journey port -> port name in port_congestion.csv (Yantian is part of Shenzhen; Nansha of Guangzhou).
CONGESTION_PORT = {
    "Yantian": "Shenzhen", "Shanghai": "Shanghai", "Ningbo": "Ningbo", "Long Beach": "Long Beach",
    "Los Angeles": "Los Angeles", "Nansha": "Guangzhou",
}


def haversine_nm(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b
    la1, lo1, la2, lo2 = map(radians, (la1, lo1, la2, lo2))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 3440.065 * asin(sqrt(h))


def build_frame() -> pd.DataFrame:
    df = pd.read_csv(JOURNEYS, parse_dates=["loaded_on", "discharged_on"])
    df = df[df["origin"].isin(COORDS) & df["destination"].isin(COORDS)].copy()
    df["lane"] = df["origin"] + ">" + df["destination"]
    df["month"] = df["loaded_on"].dt.month
    df["distance_nm"] = [haversine_nm(COORDS[o], COORDS[d]) for o, d in zip(df["origin"], df["destination"])]

    congestion = pd.read_csv(CONGESTION, parse_dates=["week_start"]).sort_values("week_start")

    def latest(port, when):
        name = CONGESTION_PORT.get(port)
        if name is None:
            return np.nan, np.nan
        recent = congestion[(congestion["port"] == name) & (congestion["week_start"] <= when)].tail(4)
        if recent.empty:
            return np.nan, np.nan
        return recent["congestion_index"].iloc[-1], recent["congestion_index"].mean()

    o = [latest(p, w) for p, w in zip(df["origin"], df["loaded_on"])]
    t = [latest(p, w) for p, w in zip(df["destination"], df["loaded_on"])]
    df["origin_cong"], df["origin_cong_4w"] = zip(*o)
    df["dest_cong"], df["dest_cong_4w"] = zip(*t)
    return df.sort_values("loaded_on").reset_index(drop=True)


def rolling_folds(df: pd.DataFrame):
    edges = [df["loaded_on"].quantile(q) for q in FOLD_START_QUANTILES] + [df["loaded_on"].max() + pd.Timedelta(days=1)]
    for i in range(len(FOLD_START_QUANTILES)):
        yield df[df["loaded_on"] < edges[i]].copy(), df[(df["loaded_on"] >= edges[i]) & (df["loaded_on"] < edges[i + 1])].copy()


def days_experiment(df: pd.DataFrame) -> dict:
    rows = []
    for train, test in rolling_folds(df):
        median = train.groupby("lane")["ocean_days"].median()
        overall = train["ocean_days"].median()
        base_test = test["lane"].map(median).fillna(overall).values

        # Leave-one-out lane median for the training targets, so a row never sees itself.
        group = train.groupby("lane")["ocean_days"]
        n, total = group.transform("count"), group.transform("sum")
        loo = ((total - train["ocean_days"]) / (n - 1)).where(n > 2, overall)
        residual = (train["ocean_days"] - loo).values

        model = lgb.LGBMRegressor(
            n_estimators=120, learning_rate=0.03, max_depth=3, num_leaves=7, min_child_samples=25,
            reg_lambda=5, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbosity=-1, random_state=42,
        ).fit(train[FEATURES], residual)
        rows.append({
            "n_test": len(test),
            "lane_median_mae": mean_absolute_error(test["ocean_days"], base_test),
            "lightgbm_mae": mean_absolute_error(test["ocean_days"], base_test + model.predict(test[FEATURES])),
        })
    frame = pd.DataFrame(rows)
    return {
        "lane_median_mae_days": round(float(frame["lane_median_mae"].mean()), 2),
        "lightgbm_mae_days": round(float(frame["lightgbm_mae"].mean()), 2),
        "folds_where_model_beat_baseline": int((frame["lightgbm_mae"] < frame["lane_median_mae"]).sum()),
    }


def delay_experiment(df: pd.DataFrame, threshold: int) -> dict:
    rows = []
    for train, test in rolling_folds(df):
        median = train.groupby("lane")["ocean_days"].median()
        overall = train["ocean_days"].median()
        train["base"] = train["lane"].map(median).fillna(overall)
        test["base"] = test["lane"].map(median).fillna(overall)
        y_train = ((train["ocean_days"] - train["base"]) >= threshold).astype(int)
        y_test = ((test["ocean_days"] - test["base"]) >= threshold).astype(int)
        if y_test.nunique() < 2:
            continue

        lane_rate = train.assign(y=y_train).groupby("lane")["y"].mean()
        baseline = test["lane"].map(lane_rate).fillna(y_train.mean())

        boosted = lgb.LGBMClassifier(
            n_estimators=150, learning_rate=0.03, max_depth=3, num_leaves=7, min_child_samples=20,
            reg_lambda=5, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbosity=-1, random_state=42,
        ).fit(train[FEATURES], y_train)

        fill = train[FEATURES].median()
        mean, std = train[FEATURES].fillna(fill).mean(), train[FEATURES].fillna(fill).std()
        logit = LogisticRegression(C=0.3, max_iter=500).fit((train[FEATURES].fillna(fill) - mean) / std, y_train)

        rows.append({
            "positive_rate": float(y_test.mean()),
            "lane_rate_auc": roc_auc_score(y_test, baseline),
            "lightgbm_auc": roc_auc_score(y_test, boosted.predict_proba(test[FEATURES])[:, 1]),
            "logistic_auc": roc_auc_score(y_test, logit.predict_proba((test[FEATURES].fillna(fill) - mean) / std)[:, 1]),
        })
    frame = pd.DataFrame(rows)
    return {
        "threshold_days": threshold,
        "test_delayed_share": round(float(frame["positive_rate"].mean()), 3),
        "lane_history_auc": round(float(frame["lane_rate_auc"].mean()), 3),
        "lightgbm_auc": round(float(frame["lightgbm_auc"].mean()), 3),
        "logistic_auc": round(float(frame["logistic_auc"].mean()), 3),
        "folds": int(len(frame)),
    }


def main() -> None:
    df = build_frame()
    lanes = df.groupby("lane").size()
    print(f"{len(df)} journeys, {len(lanes)} lanes ({int((lanes >= MIN_LANE_JOURNEYS).sum())} with >= {MIN_LANE_JOURNEYS})")

    days = days_experiment(df)
    delays = [delay_experiment(df, t) for t in DELAY_THRESHOLDS]
    print("transit days :", days)
    for d in delays:
        print(f"delayed >= {d['threshold_days']:>2} d:", d)

    best_model_auc = max(max(d["lightgbm_auc"], d["logistic_auc"]) for d in delays)
    best_baseline_auc = max(d["lane_history_auc"] for d in delays)
    model_wins = days["lightgbm_mae_days"] < days["lane_median_mae_days"] and best_model_auc > best_baseline_auc

    metrics = {
        "kind": "backtest",
        "n_journeys": int(len(df)),
        "n_lanes": int(len(lanes)),
        "folds": "rolling out-of-time (3 expanding windows)",
        "transit_days": days,
        "delayed": delays,
        "model_beats_baseline": bool(model_wins),
        "served_method": "lane statistics" if not model_wins else "lightgbm",
        "conclusion": (
            "No model predicted a journey's transit time or delay better than the lane's own history "
            "across the out-of-time folds, so the service reports lane statistics rather than a model score."
            if not model_wins else
            "A model beat the lane-history baseline across the out-of-time folds."
        ),
    }
    print("\nSaved ->", save_metrics("delay", metrics))


if __name__ == "__main__":
    main()
