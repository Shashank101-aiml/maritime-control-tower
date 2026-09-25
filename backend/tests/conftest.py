import os
import secrets

# The app refuses to start without a real secret key and a strong first-admin
# password. Tests get throwaway ones for this run only, so nothing has to be
# configured (or committed) for the suite to run, locally or in CI.
os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("FIRST_SUPERUSER_PASSWORD", secrets.token_urlsafe(18))

import pytest

from app.agents.ingestion import live_conditions_client
from app.api.dependencies.auth import get_current_active_user, get_current_active_superuser
from app.core.config import settings
from app.core.constants import UserRole
from app.main import app
from app.models.user import User


def _test_user(superuser: bool = True) -> User:
    """A stand-in principal — never touches the database."""
    user = User(
        id=1,
        email="tester@example.com",
        username="tester",
        full_name="Test User",
        hashed_password="unused",
        role=UserRole.ADMIN if superuser else UserRole.OPERATOR,
        is_active=True,
        is_superuser=superuser,
    )
    return user


@pytest.fixture(autouse=True)
def authenticated_by_default():
    """Every route is authenticated now, so the suite would otherwise be
    49 assertions about 401s.

    This overrides the auth dependency so existing tests keep exercising
    the behaviour they were written for. Tests that need to verify the
    auth boundary itself clear the override — see test_auth.py.
    """
    app.dependency_overrides[get_current_active_user] = lambda: _test_user()
    app.dependency_overrides[get_current_active_superuser] = lambda: _test_user()
    yield
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_current_active_superuser, None)


@pytest.fixture(autouse=True)
def fresh_login_guard():
    from app.core import login_guard

    login_guard.reset()
    yield
    login_guard.reset()


@pytest.fixture
def unauthenticated():
    """Drops the override so a test can assert the real 401 behaviour."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clear_conditions_cache():
    """The live client caches readings in module-level dicts, one per
    cache_key. Left alone it leaks between tests, so one test's stubbed
    readings would be served to the next."""
    live_conditions_client._caches.clear()
    yield
    live_conditions_client._caches.clear()


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
