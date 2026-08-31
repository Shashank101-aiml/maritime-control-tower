"""Unifies three congestion feature tables into one dataset by stacking
(union), not joining -- there is no shared key across them:

- congestion_features.csv: 791 vessels, global AIS loitering events,
  2012-2018, weekly grain. entity_type=vessel. Target = loiters_this_week
  (a loitering EVENT, defined upstream by a speed/duration heuristic,
  started that week).
- la_lb_visit_features.csv: 1,184 vessels, one port complex (LA/Long
  Beach), 2023 H2, per-visit grain. entity_type=vessel. Target =
  entered_waiting_area (a zone-based flag from the source pipeline).
- port_congestion.csv (cleaned): 20 real major ports, 2019-2024, weekly
  grain. entity_type=port. Target = congestion_index in the top quartile
  of its own observed distribution for that port-week (see
  CONGESTION_INDEX_QUANTILE below) -- there's no natural 0/1 event in
  this table, so the threshold is a documented, data-driven choice, not
  an arbitrary one.

Three different operational definitions of "congestion", three different
populations (vessels vs. ports), three different grains. Stacking gives
one dataset to query/explore, but a model trained across all three
without accounting for `source`/`entity_type` would be learning from
three different label definitions at once -- keep `source` (train/
evaluate per-source, or use it as a categorical feature) rather than
treating the merged `congestion_flag` as one uniform target.

Port coordinates are real, publicly-known port locations (approximate to
port/city level), not derived from any dataset in this project -- added
here because none of the raw sources include port coordinates at all.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/merge_congestion_datasets.py
"""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = REPO_ROOT / "data" / "cleaned"
FEATURES_DIR = REPO_ROOT / "data" / "features"

CONGESTION_INDEX_QUANTILE = 0.75  # "elevated congestion" = top quartile for that port

# Approximate port-center coordinates (public knowledge), keyed to the
# exact port names used in port_congestion.csv.
PORT_COORDINATES = {
    "Shanghai": (31.36, 121.50),
    "Singapore": (1.29, 103.85),
    "Rotterdam": (51.95, 4.14),
    "Los Angeles": (33.74, -118.26),
    "Long Beach": (33.75, -118.22),
    "Ningbo": (29.87, 121.54),
    "Shenzhen": (22.57, 114.27),
    "Busan": (35.10, 129.04),
    "Hong Kong": (22.34, 114.13),
    "Qingdao": (36.07, 120.38),
    "Dubai (Jebel Ali)": (25.01, 55.06),
    "Hamburg": (53.55, 9.99),
    "Antwerp": (51.22, 4.40),
    "Guangzhou": (22.75, 113.63),
    "Tanjung Pelepas": (1.36, 103.55),
    "New York": (40.67, -74.00),
    "Laem Chabang": (13.09, 100.89),
    "Tanjung Priok": (-6.10, 106.88),
    "Colombo": (6.93, 79.86),
    "Felixstowe": (51.95, 1.35),
}


def _vessel_weekly_block() -> pd.DataFrame:
    weekly = pd.read_csv(FEATURES_DIR / "congestion_features.csv", parse_dates=["week"])

    common = pd.DataFrame({
        "source": "global_loitering_weekly",
        "entity_type": "vessel",
        "label_definition": "loitering event (speed/duration heuristic) started during this week",
        "entity_id": weekly["transshipment_mmsi"].astype(str),
        "window_start": weekly["week"],
        "window_end": weekly["week"] + pd.Timedelta(days=6),
        "congestion_flag": weekly["loiters_this_week"],
        "last_lat": weekly["last_known_lat"],
        "last_lon": weekly["last_known_lon"],
        "month": weekly["month"],
        "quarter": weekly["quarter"],
    })
    specific = weekly[[
        "events_last_4w", "events_last_12w", "duration_last_4w_hours",
        "avg_speed_last_4w_knots", "cumulative_events_to_date", "weeks_since_last_event",
        "lat_grid_cell", "lon_grid_cell",
    ]]
    return pd.concat([common, specific], axis=1)


def _vessel_visit_block() -> pd.DataFrame:
    visits = pd.read_csv(
        FEATURES_DIR / "la_lb_visit_features.csv",
        parse_dates=["arrival_time", "departure_time"],
    )

    common = pd.DataFrame({
        "source": "la_lb_visit_2023h2",
        "entity_type": "vessel",
        "label_definition": "AIS-flagged waiting-area zone entered at any point during this port visit",
        "entity_id": visits["mmsi"].astype(str),
        "window_start": visits["arrival_time"],
        "window_end": visits["departure_time"],
        "congestion_flag": visits["entered_waiting_area"],
        "last_lat": visits["last_lat"],
        "last_lon": visits["last_lon"],
        "month": visits["month"],
        "quarter": visits["quarter"],
    })
    specific = visits[[
        "vessel_name", "imo", "vessel_type", "length", "width", "draft", "cargo",
        "avg_sog", "ping_count", "peak_delay_minutes", "min_distance_to_port",
        "avg_ship_density", "avg_port_throughput", "avg_port_speed",
        "visit_duration_hours", "primary_zone",
    ]]
    return pd.concat([common, specific], axis=1)


def _port_weekly_block() -> pd.DataFrame:
    ports = pd.read_csv(CLEANED_DIR / "port_congestion.csv", parse_dates=["week_start"])

    threshold = ports["congestion_index"].quantile(CONGESTION_INDEX_QUANTILE)
    ports["congestion_flag"] = (ports["congestion_index"] > threshold).astype(int)

    coords = ports["port"].map(PORT_COORDINATES)
    missing_coords = ports.loc[coords.isna(), "port"].unique()
    if len(missing_coords):
        print(f"  warning: no coordinates for ports: {list(missing_coords)}")

    common = pd.DataFrame({
        "source": "port_congestion_2019_2024",
        "entity_type": "port",
        "label_definition": f"congestion_index above the {CONGESTION_INDEX_QUANTILE:.0%}ile "
                             f"({threshold:.2f}) of its own observed distribution that week",
        "entity_id": ports["port"],
        "window_start": ports["week_start"],
        "window_end": ports["week_start"] + pd.Timedelta(days=6),
        "congestion_flag": ports["congestion_flag"],
        "last_lat": coords.map(lambda c: c[0] if isinstance(c, tuple) else None),
        "last_lon": coords.map(lambda c: c[1] if isinstance(c, tuple) else None),
        "month": ports["week_start"].dt.month,
        "quarter": ports["week_start"].dt.quarter,
    })
    # Raw same-week metrics kept for reference/analysis, but NOT safe as
    # model features -- congestion_flag was derived directly from
    # congestion_index, and the other four are definitionally the same
    # phenomenon (anchored vessels, wait time, berth delay, utilization
    # ARE congestion). Lagged/rolling versions below are the safe,
    # leading features a forecasting model should actually use.
    raw_metrics = ports[[
        "port", "country", "region", "throughput_teu_mn", "vessels_at_anchor",
        "avg_wait_days", "congestion_index", "port_utilization_pct", "berth_delay_hrs",
    ]]

    ports_sorted = ports.sort_values(["port", "week_start"])
    g = ports_sorted.groupby("port")
    lagged = pd.DataFrame(index=ports_sorted.index)
    for col in ["congestion_index", "avg_wait_days", "vessels_at_anchor", "berth_delay_hrs", "port_utilization_pct"]:
        lagged[f"{col}_lag1w"] = g[col].shift(1)
        lagged[f"{col}_roll4w_mean"] = g[col].transform(lambda s: s.rolling(4, min_periods=1).mean().shift(1))
    lagged = lagged.sort_index()

    return pd.concat([common, raw_metrics, lagged], axis=1)


def build_unified() -> pd.DataFrame:
    return pd.concat(
        [_vessel_weekly_block(), _vessel_visit_block(), _port_weekly_block()],
        axis=0, ignore_index=True,
    )


def main() -> None:
    df = build_unified()
    out_path = FEATURES_DIR / "congestion_features_unified.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows, {len(df.columns)} columns -> {out_path}")
    print(df["source"].value_counts())
    print("\ncongestion_flag rate by source:")
    print(df.groupby("source")["congestion_flag"].mean())


if __name__ == "__main__":
    main()
