from pathlib import Path
from typing import Dict, List, Optional
from typing_extensions import Annotated

from pydantic_settings import BaseSettings, NoDecode
from pydantic import AnyUrl, field_validator


class Settings(BaseSettings):
    SECRET_KEY: str = "change-this-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: AnyUrl = "sqlite:///./sql_app.db"

    # Browser origins allowed to call the API. Previously this was
    # allow_origins=["*"] together with allow_credentials=True, which is
    # invalid per the CORS spec and let any site call the API.
    # Comma-separated in .env.
    #
    # NoDecode: pydantic-settings normally tries to json.loads() a raw env
    # string for any List-typed field before _split_origins below ever
    # runs, so a plain CSV value like "a,b,c" fails at the settings-source
    # level with SettingsError -- never reaching the validator meant to
    # handle exactly that. NoDecode skips that JSON-decode attempt and
    # hands the raw string straight to _split_origins instead. This was
    # never exercised until CORS_ORIGINS was first set as a real env var
    # (previously always empty, silently falling back to the Python-list
    # default below, which needs no decoding).
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
    FIRST_SUPERUSER_USERNAME: str = "admin"
    FIRST_SUPERUSER_PASSWORD: str = "admin"
    OPENAI_API_KEY: Optional[str] = None
    WEATHER_API_KEY: Optional[str] = None
    NEWS_API_KEY: Optional[str] = None
    # A news refresh is cached this long. It costs up to 2 NewsAPI requests
    # and the free tier allows 100/day, so 3600s (<= 48/day) leaves headroom.
    NEWS_CACHE_TTL_SECONDS: int = 3600
    NEWS_LOOKBACK_DAYS: int = 7
    # Live sea-state ingestion via Open-Meteo. Needs no API key; set false
    # to run fully offline (tests, air-gapped demos).
    ENABLE_LIVE_INGESTION: bool = True
    # Free key from https://aisstream.io for live vessel positions.
    # Unset -> the AIS collector stays dormant and /api/vessels reports
    # configured: false rather than showing stale or invented vessels.
    AISSTREAM_API_KEY: Optional[str] = None

    # Operator fleets. AISStream allows at most 50 MMSIs per subscription,
    # so that is the ceiling on vessels tracked across all operators.
    FLEET_MAX_TRACKED_VESSELS: int = 50
    # How often the fleet monitoring agent re-assesses every tracked vessel.
    FLEET_MONITOR_INTERVAL_SECONDS: int = 300
    # No AIS report for this long marks a previously-seen vessel as silent.
    FLEET_POSITION_STALE_MINUTES: int = 30
    # Recent positions kept in memory per vessel for its track on the map.
    FLEET_TRAIL_POINTS: int = 60

    # Requests per minute per client IP on prediction/workflow routes.
    RATE_LIMIT_PER_MINUTE: int = 60

    # How RouteOptimizer weighs the four normalized objectives when
    # scoring candidate routes (spec's Optimization Agent explicitly
    # wants these configurable, not hardcoded). Values don't need to sum
    # to 1.0 -- RouteOptimizer normalizes by their sum at use time, so a
    # partial override (e.g. just bumping "risk") still works sensibly.
    # Same NoDecode + before-validator pattern as CORS_ORIGINS above,
    # since a Dict-typed field hits the identical json.loads()-before-
    # validator problem a List-typed one does.
    ROUTE_OPTIMIZATION_WEIGHTS: Annotated[Dict[str, float], NoDecode] = {
        "risk": 0.4,
        "cost": 0.25,
        "delay": 0.25,
        "emissions": 0.1,
    }

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        """Accept `a,b,c` from .env as well as a real list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("ROUTE_OPTIMIZATION_WEIGHTS", mode="before")
    @classmethod
    def _parse_weights(cls, value):
        """Accept `risk:0.4,cost:0.25,delay:0.25,emissions:0.1` from .env."""
        if isinstance(value, str):
            pairs = [pair.strip() for pair in value.split(",") if pair.strip()]
            return {
                key.strip(): float(raw)
                for key, raw in (pair.split(":", 1) for pair in pairs)
            }
        return value

    class Config:
        # The project's single .env lives at the repo root (backend/app/core
        # -> parents[3]). In Docker the file isn't in the image; compose
        # injects the same variables through env_file instead.
        env_file = str(Path(__file__).resolve().parents[3] / ".env")
        env_file_encoding = "utf-8"
        # The shared file also holds POSTGRES_* and VITE_* keys that
        # belong to other services, not to these settings.
        extra = "ignore"


settings = Settings()