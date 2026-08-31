import pytest

from app.agents.ingestion import live_conditions_client
from app.core.config import settings


@pytest.fixture(autouse=True)
def clear_conditions_cache():
    """The live client caches corridor readings in a module-level dict.
    Left alone it leaks between tests, so one test's stubbed readings
    would be served to the next."""
    live_conditions_client._cache["events"] = None
    live_conditions_client._cache["expires_at"] = 0.0
    yield
    live_conditions_client._cache["events"] = None
    live_conditions_client._cache["expires_at"] = 0.0


@pytest.fixture(autouse=True)
def disable_live_ingestion():
    """Keep the suite offline and deterministic.

    IngestionAgent polls the live Open-Meteo feed by default. Left on,
    every test that touches ingestion makes real network calls — slow
    (~60s for the suite), flaky when the network is down, and dependent
    on whatever the sea state happens to be. Tests exercise the local
    sample-file path instead; the live client has its own tests.
    """
    original = settings.ENABLE_LIVE_INGESTION
    settings.ENABLE_LIVE_INGESTION = False
    yield
    settings.ENABLE_LIVE_INGESTION = original
