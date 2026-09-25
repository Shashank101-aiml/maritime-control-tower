from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.fuel.reference import FUEL_ALIASES, FUELS, HUBS, LEGACY_ROUTES, SHIP_BY_NAME, WEATHER_FACTORS

# Longest realistic single voyage the estimator is asked about (round the world is ~21,600 nm).
MAX_DISTANCE_NM = 25_000


def _one_of(value: str, allowed, what: str) -> str:
    if value not in allowed:
        raise ValueError(f"unknown {what} '{value}'; choose one of: {', '.join(sorted(allowed))}")
    return value


class FuelPredictionRequest(BaseModel):
    # NaN and infinity are valid floats to JSON parsers but meaningless here.
    model_config = ConfigDict(allow_inf_nan=False)

    ship_type: str = Field(max_length=80)
    route_id: str = Field(max_length=80)
    fuel_type: str = Field(max_length=30)
    weather_conditions: str = Field(max_length=30)
    distance: float = Field(gt=0, le=MAX_DISTANCE_NM, description="Nautical miles")
    month_num: int = Field(ge=1, le=12)
    price_hub: Optional[str] = Field(default=None, max_length=10)

    @field_validator("ship_type")
    @classmethod
    def _ship(cls, v):
        return _one_of(v, SHIP_BY_NAME, "ship type")

    @field_validator("fuel_type")
    @classmethod
    def _fuel(cls, v):
        return _one_of(v, set(FUELS) | set(FUEL_ALIASES), "fuel type")

    @field_validator("weather_conditions")
    @classmethod
    def _weather(cls, v):
        return _one_of(v, WEATHER_FACTORS, "weather condition")

    @field_validator("price_hub")
    @classmethod
    def _hub(cls, v):
        return v if v is None else _one_of(v, HUBS, "price hub")
