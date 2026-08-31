from pydantic import BaseModel


class FuelPredictionRequest(BaseModel):
    ship_type: str
    route_id: str
    fuel_type: str
    weather_conditions: str
    distance: float
    month_num: int
