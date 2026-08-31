"""Builds vessel-visit-level features from the LA/Long Beach AIS parquet
(data/raw/ais_2023H2.parquet) -- 5M per-minute pings covering the San
Pedro Bay anchorage/approach complex, June-Dec 2023.

A "visit" is a vessel's continuous presence in the tracked zone: pings
from the same mmsi with no gap over VISIT_GAP_HOURS are treated as one
visit; a gap that long means the vessel actually left and came back.
Median ping interval in this data is 3 minutes, so 12 hours is a
generous, well-separated cutoff (confirmed by inspecting the gap
distribution -- see pipeline notes).

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/build_la_lb_visit_features.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
FEATURES_DIR = REPO_ROOT / "data" / "features"

VISIT_GAP_HOURS = 12

PING_COLUMNS = [
    "mmsi", "visit_id", "base_date_time", "longitude", "latitude", "sog", "cog", "heading",
    "vessel_name", "imo", "vessel_type", "length", "width", "draft", "cargo",
    "is_in_waiting_area", "delay_minutes", "distance_to_port", "ship_density",
    "port_throughput", "avg_port_speed",
]


def _segment_visits(df: pd.DataFrame) -> pd.Series:
    """Assigns a running visit number per mmsi, incrementing whenever the
    gap since the previous ping (for that vessel) exceeds VISIT_GAP_HOURS."""
    gap_minutes = df.groupby("mmsi")["base_date_time"].diff().dt.total_seconds() / 60
    new_visit = (gap_minutes.isna()) | (gap_minutes > VISIT_GAP_HOURS * 60)
    return new_visit.groupby(df["mmsi"]).cumsum()


def build_features() -> pd.DataFrame:
    df = pd.read_parquet(RAW_DIR / "ais_2023H2.parquet", columns=PING_COLUMNS)
    df = df.sort_values(["mmsi", "base_date_time"]).reset_index(drop=True)

    df["visit_number"] = _segment_visits(df)

    grouped = df.groupby(["mmsi", "visit_number"])
    visits = grouped.agg(
        arrival_time=("base_date_time", "min"),
        departure_time=("base_date_time", "max"),
        ping_count=("base_date_time", "count"),
        vessel_name=("vessel_name", "first"),
        imo=("imo", "first"),
        vessel_type=("vessel_type", lambda s: s.mode().iloc[0] if not s.mode().empty else np.nan),
        length=("length", "median"),
        width=("width", "median"),
        draft=("draft", "median"),
        cargo=("cargo", lambda s: s.mode().iloc[0] if not s.mode().empty else np.nan),
        avg_sog=("sog", "mean"),
        entered_waiting_area=("is_in_waiting_area", "max"),
        peak_delay_minutes=("delay_minutes", "max"),
        min_distance_to_port=("distance_to_port", "min"),
        avg_ship_density=("ship_density", "mean"),
        avg_port_throughput=("port_throughput", "mean"),
        avg_port_speed=("avg_port_speed", "mean"),
        last_lat=("latitude", "last"),
        last_lon=("longitude", "last"),
        primary_zone=("visit_id", lambda s: s.mode().iloc[0] if not s.mode().empty else np.nan),
    ).reset_index()

    visits["visit_duration_hours"] = (
        (visits["departure_time"] - visits["arrival_time"]).dt.total_seconds() / 3600
    )
    # NaN survives here (nullable Int64) for the rare visit where every ping
    # had a missing is_in_waiting_area reading -- genuinely unknown, not False
    visits["entered_waiting_area"] = visits["entered_waiting_area"].astype("Int64")
    visits["month"] = visits["arrival_time"].dt.month
    visits["quarter"] = visits["arrival_time"].dt.quarter

    # drop single-ping "visits" -- almost certainly a vessel passing through
    # or an isolated AIS message, not a real port call
    visits = visits[visits["ping_count"] > 1].reset_index(drop=True)

    return visits.drop(columns=["visit_number"])


def main() -> None:
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    df = build_features()
    out_path = FEATURES_DIR / "la_lb_visit_features.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows, {len(df.columns)} columns -> {out_path}")
    print(f"Vessels: {df['mmsi'].nunique()}")
    print(f"entered_waiting_area rate: {df['entered_waiting_area'].mean():.3f}")
    print(f"visit_duration_hours describe:\n{df['visit_duration_hours'].describe()}")


if __name__ == "__main__":
    main()
