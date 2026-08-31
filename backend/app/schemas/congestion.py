from typing import Literal, Optional

from pydantic import BaseModel


class CongestionPredictionRequest(BaseModel):
    entity_type: Literal["vessel", "port"]
    source: Literal["global_loitering_weekly", "la_lb_visit_2023h2", "port_congestion_2019_2024"]
    last_lat: Optional[float] = None
    last_lon: Optional[float] = None
    month: int
    quarter: int

    # global_loitering_weekly fields
    events_last_4w: Optional[float] = None
    events_last_12w: Optional[float] = None
    duration_last_4w_hours: Optional[float] = None
    avg_speed_last_4w_knots: Optional[float] = None
    cumulative_events_to_date: Optional[float] = None
    weeks_since_last_event: Optional[float] = None
    lat_grid_cell: Optional[float] = None
    lon_grid_cell: Optional[float] = None

    # la_lb_visit_2023h2 fields (static vessel specs)
    vessel_type: Optional[float] = None
    length: Optional[float] = None
    width: Optional[float] = None
    draft: Optional[float] = None
    cargo: Optional[float] = None

    # port_congestion_2019_2024 fields (lagged, not same-week)
    region: Optional[str] = None
    congestion_index_lag1w: Optional[float] = None
    congestion_index_roll4w_mean: Optional[float] = None
    avg_wait_days_lag1w: Optional[float] = None
    avg_wait_days_roll4w_mean: Optional[float] = None
    vessels_at_anchor_lag1w: Optional[float] = None
    vessels_at_anchor_roll4w_mean: Optional[float] = None
    berth_delay_hrs_lag1w: Optional[float] = None
    berth_delay_hrs_roll4w_mean: Optional[float] = None
    port_utilization_pct_lag1w: Optional[float] = None
    port_utilization_pct_roll4w_mean: Optional[float] = None
