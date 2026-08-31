"""Builds the vessel x time-window feature table for the congestion model
(predicting whether a vessel will have a loitering event in a given week).

Grain: one row per (mmsi, week). Source: data/cleaned/loitering_events.csv
only. ais_vessel_states.csv and ships.csv were NOT usable here — their
vessel populations barely overlap with loitering_events.csv's 791 vessels
(only 4 shared MMSIs with ais_vessel_states, none with ships.csv, which
has no MMSI at all), so there's no valid key to join vessel specs onto
these events. Every feature is instead derived from the vessel's own past
loitering history: a "behavioral profile" built from history, not a
static specs join.

Anti-leakage rule: every feature for week t is computed strictly from
weeks < t (rolling/lag features are shift(1)'d after the rolling window).
Only the target column looks at week t itself.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/build_congestion_features.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = REPO_ROOT / "data" / "cleaned"
FEATURES_DIR = REPO_ROOT / "data" / "features"

LAT_LON_GRID_SIZE_DEGREES = 10  # coarse geospatial bucket; no geocoding service available


def _weekly_grid(events: pd.DataFrame) -> pd.DataFrame:
    """One row per (mmsi, week) spanning each vessel's own first-to-last
    observed week -- not the global date range, so vessels that were only
    tracked for a short span don't get thousands of empty rows."""
    rows = []
    for mmsi, group in events.groupby("transshipment_mmsi"):
        weeks = pd.date_range(
            group["start_week"].min(), group["start_week"].max(), freq="W-MON"
        )
        rows.append(pd.DataFrame({"transshipment_mmsi": mmsi, "week": weeks}))
    return pd.concat(rows, ignore_index=True)


def build_features() -> pd.DataFrame:
    events = pd.read_csv(
        CLEANED_DIR / "loitering_events.csv",
        parse_dates=["starting_timestamp", "ending_timestamp"],
    )
    events["start_week"] = (
        events["starting_timestamp"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    )

    grid = _weekly_grid(events)

    # --- Target: did this vessel start a loitering event in this week? ---
    weekly_events = (
        events.groupby(["transshipment_mmsi", "start_week"])
        .agg(
            event_count=("starting_timestamp", "count"),
            total_duration_hours=("total_event_duration", "sum"),
            avg_speed_knots=("median_speed_knots", "mean"),
            last_lat=("ending_latitude", "last"),
            last_lon=("ending_longitude", "last"),
        )
        .reset_index()
        .rename(columns={"start_week": "week"})
    )

    df = grid.merge(weekly_events, on=["transshipment_mmsi", "week"], how="left")
    df["loiters_this_week"] = (df["event_count"].fillna(0) > 0).astype(int)

    df = df.sort_values(["transshipment_mmsi", "week"]).reset_index(drop=True)
    g = df.groupby("transshipment_mmsi")

    # --- Temporal features: strictly-past rolling/lag aggregates ---
    event_count_filled = df["event_count"].fillna(0)
    duration_filled = df["total_duration_hours"].fillna(0)

    df["events_last_4w"] = g["event_count"].transform(
        lambda s: s.fillna(0).rolling(4, min_periods=1).sum().shift(1)
    )
    df["events_last_12w"] = g["event_count"].transform(
        lambda s: s.fillna(0).rolling(12, min_periods=1).sum().shift(1)
    )
    df["duration_last_4w_hours"] = g["total_duration_hours"].transform(
        lambda s: s.fillna(0).rolling(4, min_periods=1).sum().shift(1)
    )
    df["avg_speed_last_4w_knots"] = g["avg_speed_knots"].transform(
        lambda s: s.rolling(4, min_periods=1).mean().shift(1)
    )
    df["cumulative_events_to_date"] = g["event_count"].transform(
        lambda s: s.fillna(0).cumsum().shift(1)
    )

    had_event = (df["event_count"].fillna(0) > 0).astype(int)
    df["_had_event"] = had_event
    df["weeks_since_last_event"] = g["_had_event"].transform(_weeks_since_last)
    df = df.drop(columns=["_had_event"])

    # --- Geospatial features: last known position, carried forward from
    # the most recent PRIOR event (not this week's, to avoid leakage) ---
    df["last_known_lat"] = g["last_lat"].transform(lambda s: s.shift(1).ffill())
    df["last_known_lon"] = g["last_lon"].transform(lambda s: s.shift(1).ffill())
    df["lat_grid_cell"] = (df["last_known_lat"] // LAT_LON_GRID_SIZE_DEGREES).astype("Int64")
    df["lon_grid_cell"] = (df["last_known_lon"] // LAT_LON_GRID_SIZE_DEGREES).astype("Int64")

    # --- Calendar features (known in advance, not a leak) ---
    df["month"] = df["week"].dt.month
    df["quarter"] = df["week"].dt.quarter

    feature_columns = [
        "transshipment_mmsi", "week",
        "events_last_4w", "events_last_12w", "duration_last_4w_hours",
        "avg_speed_last_4w_knots", "cumulative_events_to_date", "weeks_since_last_event",
        "last_known_lat", "last_known_lon", "lat_grid_cell", "lon_grid_cell",
        "month", "quarter",
        "loiters_this_week",
    ]
    return df[feature_columns]


def _weeks_since_last(had_event: pd.Series) -> pd.Series:
    """For each row, how many weeks since the last row (strictly before
    it) where had_event was 1. NaN if no prior event exists yet."""
    result = np.full(len(had_event), np.nan)
    last_event_idx = None
    values = had_event.to_numpy()
    for i in range(len(values)):
        if last_event_idx is not None:
            result[i] = i - last_event_idx
        if values[i] == 1:
            last_event_idx = i
    return pd.Series(result, index=had_event.index)


def main() -> None:
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    df = build_features()
    out_path = FEATURES_DIR / "congestion_features.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows, {len(df.columns)} columns -> {out_path}")
    print(f"Vessels: {df['transshipment_mmsi'].nunique()}")
    print(f"Positive rate (loiters_this_week=1): {df['loiters_this_week'].mean():.3f}")


if __name__ == "__main__":
    main()
