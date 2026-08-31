from typing import Optional

from pydantic import BaseModel


class DelayPredictionRequest(BaseModel):
    origin_port: str
    destination_port: str
    carrier: str
    service_level: str
    customer: str
    plant_code: str
    tpt: int
    unit_quantity: int
    weight: float
    freight_rate: Optional[float] = None
    freight_min_cost: Optional[float] = None
    wh_cost_per_unit: Optional[float] = None
    wh_daily_capacity: Optional[int] = None
    plant_week_order_count: Optional[int] = None
    backlog_vs_capacity: Optional[float] = None
    is_vmi_customer_anywhere: bool = False
