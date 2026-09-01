from typing import List, Optional
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