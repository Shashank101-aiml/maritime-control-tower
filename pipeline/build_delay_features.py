"""Builds the shipment-level feature table for the delay model (predicting
whether/how many days an order will ship late).

Grain: one row per order (data/cleaned/supply_chain/order_list.csv).
Joined against the other supply-chain sheets via their real shared keys
(Plant Code, Carrier, Customer) -- this is a genuine relational dataset,
unlike the congestion side, so no synthetic joins are needed here.

Anti-leakage: 'ship_ahead_day_count' is dropped. It and the target
'ship_late_day_count' are two views of the same post-shipment outcome
(how many days early/late the order actually shipped) -- knowing one
gives away the other, so keeping both as features would leak the label.

Origin/Destination Port are the synthetic PORT01-PORT10 codes from this
dataset (unrelated to real-world port names/coordinates elsewhere in the
project) -- kept as categorical route identifiers, not treated as
geospatial, since there's no real geography behind them.

Run from the repo root with the backend venv:
    backend/.venv/Scripts/python.exe pipeline/build_delay_features.py
"""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SUPPLY_CHAIN_DIR = REPO_ROOT / "data" / "cleaned" / "supply_chain"
FEATURES_DIR = REPO_ROOT / "data" / "features"


def build_features() -> pd.DataFrame:
    orders = pd.read_csv(SUPPLY_CHAIN_DIR / "order_list.csv", parse_dates=["order_date"])
    freight = pd.read_csv(SUPPLY_CHAIN_DIR / "freight_rates.csv")
    wh_costs = pd.read_csv(SUPPLY_CHAIN_DIR / "wh_costs.csv")
    wh_capacities = pd.read_csv(SUPPLY_CHAIN_DIR / "wh_capacities.csv")
    vmi_customers = pd.read_csv(SUPPLY_CHAIN_DIR / "vmi_customers.csv")

    df = orders.drop(columns=["ship_ahead_day_count"])

    # --- Static: freight rate context for this carrier/route/service level ---
    freight_agg = (
        freight.groupby(["carrier", "orig_port_cd", "dest_port_cd", "svc_cd"])
        .agg(freight_rate=("rate", "mean"), freight_min_cost=("minimum_cost", "mean"))
        .reset_index()
    )
    df = df.merge(
        freight_agg,
        left_on=["carrier", "origin_port", "destination_port", "service_level"],
        right_on=["carrier", "orig_port_cd", "dest_port_cd", "svc_cd"],
        how="left",
    ).drop(columns=["orig_port_cd", "dest_port_cd", "svc_cd"])

    # --- Static: plant-level warehouse cost/capacity ---
    df = df.merge(
        wh_costs.rename(columns={"wh": "plant_code", "cost_per_unit": "wh_cost_per_unit"}),
        on="plant_code", how="left",
    )
    df = df.merge(
        wh_capacities.rename(columns={"plant_id": "plant_code", "daily_capacity": "wh_daily_capacity"}),
        on="plant_code", how="left",
    )

    # --- Static: is this customer VMI (vendor-managed inventory) anywhere?
    # vmi_customers.csv pairs specific (plant, customer) relationships, but
    # none of those exact pairs occur in this order snapshot -- the 8
    # customers that do appear ship through a *different* plant than the
    # one where they're VMI-managed. A strict (plant, customer) match would
    # be a constant, always-False column, so this uses customer-only
    # matching instead: "is this customer VMI-managed somewhere," a looser
    # but non-degenerate signal. ---
    vmi_customer_names = set(vmi_customers["customers"])
    df["is_vmi_customer_anywhere"] = df["customer"].isin(vmi_customer_names)

    # --- Temporal: calendar features + same-week order backlog per plant ---
    df["order_month"] = df["order_date"].dt.month
    df["order_day_of_week"] = df["order_date"].dt.dayofweek
    df["order_week"] = df["order_date"].dt.to_period("W-SUN").dt.start_time

    backlog = (
        df.groupby(["plant_code", "order_week"]).size().rename("plant_week_order_count")
    )
    df = df.merge(backlog, on=["plant_code", "order_week"], how="left")
    # capacity pressure: how many orders this week vs. the plant's daily capacity
    df["backlog_vs_capacity"] = df["plant_week_order_count"] / df["wh_daily_capacity"].replace(0, pd.NA)

    # --- Target ---
    df["is_late"] = (df["ship_late_day_count"] > 0).astype(int)

    df = df.drop(columns=["order_week"])
    return df


def main() -> None:
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    df = build_features()
    out_path = FEATURES_DIR / "delay_features.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows, {len(df.columns)} columns -> {out_path}")
    print(f"is_late rate: {df['is_late'].mean():.4f}")
    print(f"freight_rate missing: {df['freight_rate'].isna().mean():.3f}")


if __name__ == "__main__":
    main()
