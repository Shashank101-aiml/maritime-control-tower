"""Cleans every raw dataset in data/raw/ and writes normalized versions to
data/cleaned/. One function per source dataset, each documenting the actual
data-quality issue it fixes (found by profiling data/raw/ directly) rather
than applying generic boilerplate cleaning.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/clean_datasets.py
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
CLEANED_DIR = REPO_ROOT / "data" / "cleaned"

AIS_HEADING_UNAVAILABLE = 359.9  # anything above this (incl. the AIS sentinel 511) is not a real heading
AIS_SPEED_UNAVAILABLE = 102.3  # AIS sentinel meaning "speed not available"


def _to_snake_case(name: str) -> str:
    name = name.strip().replace(" ", "_").replace("/", "_per_")
    name = re.sub(r"[^0-9a-zA-Z_]", "", name)
    return re.sub(r"_+", "_", name).strip("_").lower()


def clean_ships() -> pd.DataFrame:
    """Cleaned_ships_data.csv is already well-formed (no missing values, no
    duplicates) — just normalize column names and strip stray whitespace."""
    df = pd.read_csv(RAW_DIR / "Cleaned_ships_data.csv")
    df.columns = [_to_snake_case(c) for c in df.columns]
    for col in df.select_dtypes(include=["object", "str"]).columns:
        df[col] = df[col].str.strip()
    return df


def clean_ports() -> pd.DataFrame:
    """Port_locations.csv is 95% duplicate rows (5,856 rows -> 293 unique
    port records) and has inconsistent whitespace/casing."""
    df = pd.read_csv(RAW_DIR / "Port_locations.csv")
    df.columns = [_to_snake_case(c) for c in df.columns]
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    df["locode"] = df["locode"].str.upper()
    df = df.drop_duplicates().reset_index(drop=True)
    return df


def clean_ais_vessel_states() -> pd.DataFrame:
    """ais_data.csv issues found by profiling:
    - unnamed index column left over from a prior export
    - heading uses AIS sentinel values (>359.9, e.g. 511) for "not available"
    - sog uses the AIS sentinel 102.3 for "not available"; observed max of
      214 knots is not a physically plausible vessel speed
    - mmsi should always be a 9-digit identifier; 7-8 digit values are
      malformed/truncated
    Invalid sentinel values are converted to NaN (not imputed — that's a
    modeling-time decision); malformed mmsi rows are dropped since the
    vessel can't be reliably identified.
    """
    df = pd.read_csv(RAW_DIR / "ais_data.csv")
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])
    df.columns = [_to_snake_case(c) for c in df.columns]

    df = df[df["mmsi"].astype(str).str.len() == 9].copy()

    df.loc[df["heading"] > AIS_HEADING_UNAVAILABLE, "heading"] = np.nan
    df.loc[df["sog"] >= AIS_SPEED_UNAVAILABLE, "sog"] = np.nan

    df["navigationalstatus"] = df["navigationalstatus"].replace("Unknown value", "Unknown")
    for col in ("navigationalstatus", "shiptype"):
        df[col] = df[col].str.strip()

    return df.reset_index(drop=True)


def clean_loitering_events() -> pd.DataFrame:
    """loitering-events.csv has 184 exact duplicate rows and string
    timestamps; parses timestamps to real datetimes and validates that
    every event ends after it starts."""
    df = pd.read_csv(RAW_DIR / "loitering-events.csv")
    df.columns = [_to_snake_case(c) for c in df.columns]
    df = df.drop_duplicates().reset_index(drop=True)

    for col in ("starting_timestamp", "ending_timestamp"):
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    invalid_order = df["ending_timestamp"] <= df["starting_timestamp"]
    if invalid_order.any():
        print(f"  loitering_events: dropping {invalid_order.sum()} rows where ending_timestamp <= starting_timestamp")
        df = df[~invalid_order]

    return df.reset_index(drop=True)


def clean_fuel_efficiency() -> pd.DataFrame:
    """ship-fuel-efficiency.csv has no missing values or duplicates —
    normalize column names and add a numeric month for ML use (the
    original 'month' has no year, so it stays a categorical, not a date)."""
    df = pd.read_csv(RAW_DIR / "ship-fuel-efficiency.csv", sep="\t")
    df.columns = [_to_snake_case(c) for c in df.columns]

    month_order = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    df["month_num"] = df["month"].map({m: i + 1 for i, m in enumerate(month_order)})

    return df


def clean_maritime_volume() -> pd.DataFrame:
    """maritime_volume.csv is an OECD-style wide export: a title row, a
    header row (YEAR + year columns), then region/series rows where the
    region's hierarchy depth (World > continent > sub-region > ...) is
    encoded as leading whitespace. Reshapes it from wide (one column per
    year) to a proper long-form time series."""
    raw = pd.read_csv(RAW_DIR / "maritime_volume.csv", sep="\t", header=None, engine="python")

    year_columns = raw.iloc[1, 2:].tolist()
    data = raw.iloc[2:].copy()
    data.columns = ["region_raw", "series", *year_columns]
    data = data.dropna(subset=["region_raw"])

    data["region_level"] = data["region_raw"].str.len() - data["region_raw"].str.lstrip().str.len()
    data["region_level"] = (data["region_level"] // 2).astype(int)
    data["region"] = data["region_raw"].str.strip()
    data = data.drop(columns=["region_raw"])

    long_df = data.melt(
        id_vars=["region", "region_level", "series"],
        var_name="year",
        value_name="metric_tons_millions",
    )
    long_df["year"] = long_df["year"].astype(int)
    long_df["metric_tons_millions"] = pd.to_numeric(long_df["metric_tons_millions"], errors="coerce")
    long_df = long_df.dropna(subset=["metric_tons_millions"])

    return long_df.sort_values(["region", "series", "year"]).reset_index(drop=True)


def clean_container_tracking() -> pd.DataFrame:
    """Container Tracking Data.xlsx issues found by profiling:
    - 'Another NEW Predicated Delivery Date' is 100% the literal string
      '?' (zero information) -> dropped entirely
    - PORT_OF_LOADING_DATE parses as `object` dtype (mixed formatting)
      while its sibling date columns parse as real datetimes -> re-parsed
      explicitly with coercion
    - DELIVERED_FLAG is 'Yes'/NaN -> converted to an actual boolean
    """
    df = pd.read_excel(RAW_DIR / "Container Tracking Data.xlsx", sheet_name="Data with Main Column")
    df = df.drop(columns=["Another NEW Predicated Delivery Date"])
    df.columns = [_to_snake_case(c) for c in df.columns]

    date_columns = [c for c in df.columns if c.endswith("_date") or c == "last_tracked_with_vessel"]
    for col in date_columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df["delivered"] = df["delivered_flag"].eq("Yes")
    df = df.drop(columns=["delivered_flag"])

    for col in df.select_dtypes(include=["object", "str"]).columns:
        df[col] = df[col].str.strip()

    return df


def clean_port_congestion() -> pd.DataFrame:
    """port_congestion.csv is already well-formed (no missing values, no
    duplicates) -- just normalize column names/casing."""
    df = pd.read_csv(RAW_DIR / "port_congestion.csv")
    df.columns = [_to_snake_case(c) for c in df.columns]
    for col in df.select_dtypes(include=["object", "str"]).columns:
        df[col] = df[col].str.strip()
    return df


def clean_supply_chain() -> dict:
    """Supply chain logisitcs problem.xlsx: 7 relational sheets. Kept as
    separate normalized tables (join at feature-engineering time, not
    here) rather than forced into one wide table. Only real issues:
    Order ID stored as float64 (whole numbers) and 3 duplicate rows in
    FreightRates."""
    path = RAW_DIR / "Supply chain logisitcs problem.xlsx"
    xl = pd.ExcelFile(path)

    def _clean_sheet(sheet_name: str) -> pd.DataFrame:
        sheet_df = xl.parse(sheet_name)
        sheet_df.columns = [_to_snake_case(c) for c in sheet_df.columns]
        sheet_df = sheet_df.drop_duplicates().reset_index(drop=True)
        for col in sheet_df.select_dtypes(include=["object", "str"]).columns:
            sheet_df[col] = sheet_df[col].str.strip()
        return sheet_df

    tables = {
        "order_list": _clean_sheet("OrderList"),
        "freight_rates": _clean_sheet("FreightRates"),
        "wh_costs": _clean_sheet("WhCosts"),
        "wh_capacities": _clean_sheet("WhCapacities"),
        "products_per_plant": _clean_sheet("ProductsPerPlant"),
        "vmi_customers": _clean_sheet("VmiCustomers"),
        "plant_ports": _clean_sheet("PlantPorts"),
    }
    tables["order_list"]["order_id"] = tables["order_list"]["order_id"].astype("int64")
    return tables


def main() -> None:
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    (CLEANED_DIR / "supply_chain").mkdir(parents=True, exist_ok=True)

    jobs = {
        "ships.csv": clean_ships,
        "ports.csv": clean_ports,
        "ais_vessel_states.csv": clean_ais_vessel_states,
        "loitering_events.csv": clean_loitering_events,
        "fuel_efficiency.csv": clean_fuel_efficiency,
        "maritime_volume.csv": clean_maritime_volume,
        "container_tracking.csv": clean_container_tracking,
        "port_congestion.csv": clean_port_congestion,
    }

    for filename, fn in jobs.items():
        print(f"Cleaning -> {filename}")
        df = fn()
        df.to_csv(CLEANED_DIR / filename, index=False)
        print(f"  {len(df)} rows, {len(df.columns)} columns")

    print("Cleaning -> supply_chain/*.csv")
    for table_name, table_df in clean_supply_chain().items():
        table_df.to_csv(CLEANED_DIR / "supply_chain" / f"{table_name}.csv", index=False)
        print(f"  {table_name}: {len(table_df)} rows, {len(table_df.columns)} columns")


if __name__ == "__main__":
    main()
