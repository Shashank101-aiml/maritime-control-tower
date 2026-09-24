"""Cleans the real container-tracking export into per-journey ocean transit
times, with an exact accounting of every row it drops.

Input:  data/cleaned/container_tracking.csv  (real container journeys)
Output: data/features/transit_journeys.csv          one row per usable ocean leg
        data/features/transit_journeys_summary.json  what was kept and why the rest wasn't

A journey's ocean transit is the days from `port_of_loading_date` to
`port_of_discharge_date`. The export's dates are messy -- typo'd years
(1900, 2005), discharge dates before loading, and so on -- so a row is kept
only when both ports and both dates exist, the sailing is between
MIN_OCEAN_DAYS and MAX_OCEAN_DAYS, and it was loaded inside the real
LOAD_WINDOW. Nothing is repaired or guessed: a row that can't be trusted is
dropped and counted.

Run from the repo root:
    python pipeline/build_transit_journeys.py
"""

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "data" / "cleaned" / "container_tracking.csv"
OUT_DIR = REPO_ROOT / "data" / "features"

MIN_OCEAN_DAYS, MAX_OCEAN_DAYS = 3, 150
LOAD_WINDOW = ("2020-01-01", "2022-12-31")

# Spellings of the same port in the export.
PORT_ALIASES = {
    "Tianjin Xin Gang": "Tianjin Xingang",
    "Cai Mep International Terminal": "Cai Mep",
    "Qingdao Shi": "Qingdao",
}


def port_name(value: pd.Series) -> pd.Series:
    """'Yantian, Guangdong Sheng, China' -> 'Yantian'."""
    return value.fillna("").str.split(",").str[0].str.strip().replace(PORT_ALIASES)


def main() -> None:
    df = pd.read_csv(SOURCE)
    total = len(df)
    dropped = {}

    df["loaded_on"] = pd.to_datetime(df["port_of_loading_date"], errors="coerce")
    df["discharged_on"] = pd.to_datetime(df["port_of_discharge_date"], errors="coerce")
    df["origin"] = port_name(df["port_of_loading"])
    df["destination"] = port_name(df["port_of_discharge"])

    def keep(mask: pd.Series, reason: str) -> None:
        nonlocal df
        dropped[reason] = int((~mask).sum())
        df = df[mask]

    keep((df["origin"] != "") & (df["destination"] != ""), "missing loading or discharge port")
    keep(df["loaded_on"].notna() & df["discharged_on"].notna(), "missing loading or discharge date")
    df = df.assign(ocean_days=(df["discharged_on"] - df["loaded_on"]).dt.days)
    keep(df["ocean_days"].between(MIN_OCEAN_DAYS, MAX_OCEAN_DAYS),
         f"ocean transit outside {MIN_OCEAN_DAYS}-{MAX_OCEAN_DAYS} days (bad dates)")
    keep(df["loaded_on"].between(*LOAD_WINDOW), f"loaded outside {LOAD_WINDOW[0]} to {LOAD_WINDOW[1]} (typo'd years)")
    keep(df["origin"] != df["destination"], "same loading and discharge port")

    out = df[["origin", "destination", "loaded_on", "discharged_on", "ocean_days"]].sort_values("loaded_on")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_DIR / "transit_journeys.csv", index=False, date_format="%Y-%m-%d")

    lanes = out.groupby(["origin", "destination"]).size()
    summary = {
        "source": str(SOURCE.relative_to(REPO_ROOT)).replace("\\", "/"),
        "rows_in": total,
        "rows_kept": int(len(out)),
        "dropped": dropped,
        "lanes": int(len(lanes)),
        "loaded_from": out["loaded_on"].min().strftime("%Y-%m-%d"),
        "loaded_to": out["loaded_on"].max().strftime("%Y-%m-%d"),
    }
    (OUT_DIR / "transit_journeys_summary.json").write_text(json.dumps(summary, indent=2))

    print(f"{total} rows in -> {len(out)} kept across {len(lanes)} lanes")
    for reason, count in dropped.items():
        print(f"  dropped {count:4d}: {reason}")


if __name__ == "__main__":
    main()
