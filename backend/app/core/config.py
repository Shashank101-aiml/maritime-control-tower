from typing import List, Optional

from pydantic_settings import BaseSettings
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
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
    FIRST_SUPERUSER_USERNAME: str = "admin"
    FIRST_SUPERUSER_PASSWORD: str = "admin"
    OPENAI_API_KEY: Optional[str] = None
    WEATHER_API_KEY: Optional[str] = None
    NEWS_API_KEY: Optional[str] = None
    # Live sea-state ingestion via Open-Meteo. Needs no API key; set false
    # to run fully offline (tests, air-gapped demos).
    ENABLE_LIVE_INGESTION: bool = True
    # Free key from https://aisstream.io for live vessel positions.
    # Unset -> the AIS collector stays dormant and /api/vessels reports
    # configured: false rather than showing stale or invented vessels.
    AISSTREAM_API_KEY: Optional[str] = None

    # Requests per minute per client IP on prediction/workflow routes.
    RATE_LIMIT_PER_MINUTE: int = 60

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        """Accept `a,b,c` from .env as well as a real list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()