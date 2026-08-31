from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import AnyUrl


class Settings(BaseSettings):
    SECRET_KEY: str = "change-this-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: AnyUrl = "sqlite:///./sql_app.db"
    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()