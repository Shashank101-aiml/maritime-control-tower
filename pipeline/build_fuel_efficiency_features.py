"""Builds the fuel-efficiency / cost-savings feature table (the third
predictive pillar alongside congestion and delay).

Grain: one row per (ship_id, route_id, month) trip record, straight from
data/cleaned/fuel_efficiency.csv (120 ships x 12 months = 1,440 rows,
already clean). Primary target: fuel_consumption -- "how much fuel will
this trip use, given ship/route/weather conditions" is the actionable
prediction a cost-savings product needs; CO2_emissions and
engine_efficiency are kept as auxiliary columns, not separate targets,
since fuel_consumption drives both.

Cost figures use FIXED, DOCUMENTED reference bunker prices per liter
(HFO ~$0.55/L, Diesel ~$0.80/L -- representative of real 2023-2024 bunker
price ranges converted from USD/ton, not a live feed) since no per-trip
fuel price exists in this dataset. `fuel_consumption`'s unit isn't
documented in the source, but the observed magnitudes only make sense as
liters -- a "Fishing Trawler" or "Surfer Boat" averaging ~2,000-3,000
*tons* per month would be absurd for a small vessel, but is entirely
plausible as liters (a few tons). Treat estimated_cost_usd /
cost_savings_potential_usd as illustrative, not financial-grade figures.

cost_savings_potential_usd is derived, not fabricated: for each
(ship_type, route_id) group, it benchmarks against the best (lowest)
fuel-per-distance ratio actually observed in that group, and reports how
much more this specific trip cost versus that realistic best case.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/build_fuel_efficiency_features.py
"""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = REPO_ROOT / "data" / "cleaned"
FEATURES_DIR = REPO_ROOT / "data" / "features"

# Illustrative reference bunker fuel prices (USD/liter), not a live feed.
# fuel_consumption's unit is undocumented in the source but its magnitude
# (see module docstring) only makes sense as liters, not metric tons.
FUEL_PRICE_USD_PER_LITER = {
    "HFO": 0.55,
    "Diesel": 0.80,
}


def build_features() -> pd.DataFrame:
    df = pd.read_csv(CLEANED_DIR / "fuel_efficiency.csv")

    df["fuel_per_distance"] = df["fuel_consumption"] / df["distance"]
    df["co2_per_distance"] = df["co2_emissions"] / df["distance"]

    df["price_per_liter"] = df["fuel_type"].map(FUEL_PRICE_USD_PER_LITER)
    df["estimated_cost_usd"] = df["fuel_consumption"] * df["price_per_liter"]

    benchmark = (
        df.groupby(["ship_type", "route_id"])["fuel_per_distance"]
        .transform("min")
    )
    df["benchmark_fuel_per_distance"] = benchmark
    df["benchmark_cost_usd"] = benchmark * df["distance"] * df["price_per_liter"]
    df["cost_savings_potential_usd"] = (
        df["estimated_cost_usd"] - df["benchmark_cost_usd"]
    ).clip(lower=0)

    return df


def main() -> None:
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    df = build_features()
    out_path = FEATURES_DIR / "fuel_efficiency_features.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows, {len(df.columns)} columns -> {out_path}")
    print(f"fuel_consumption describe:\n{df['fuel_consumption'].describe()}")
    print(f"\ncost_savings_potential_usd describe:\n{df['cost_savings_potential_usd'].describe()}")
    print(f"\ntotal illustrative cost_savings_potential across all trips: ${df['cost_savings_potential_usd'].sum():,.0f}")


if __name__ == "__main__":
    main()
