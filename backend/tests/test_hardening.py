"""Password policy, first-admin seeding, login lockout, secret-key validation,
and the input validation added to the fuel, route and governance endpoints."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main_module
from app.core import login_guard
from app.core.config import Settings
from app.core.passwords import check_password_strength
from app.main import app
from app.models.user import User

from tests.fleet_support import make_engine_and_session, make_user

client = TestClient(app)
with client:
    pass


# --- password policy ------------------------------------------------------

@pytest.mark.parametrize("bad", ["admin", "short1!", "change-me-please", "aaaaaaaaaaaaaaaa", "PASSWORD", "administrator"])
def test_weak_passwords_are_refused(bad):
    assert check_password_strength(bad, "admin") is not None


def test_a_password_containing_the_username_is_refused():
    assert "username" in check_password_strength("my-admin-account-1", "admin")


def test_a_long_random_password_passes():
    assert check_password_strength("Vq7-plum-harbor-92", "admin") is None


# --- secret key -----------------------------------------------------------

@pytest.mark.parametrize("key", ["", "change-this-secret", "change-me-generate-with-secrets", "tooshort"])
def test_a_missing_or_weak_secret_key_stops_the_app_starting(key):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(SECRET_KEY=key, _env_file=None)


def test_a_long_random_secret_key_is_accepted():
    assert Settings(SECRET_KEY="x" * 8 + "Qw3rtyUiop-Asdfghjkl-Zxcvbnm-1234", _env_file=None).SECRET_KEY


# --- first admin ----------------------------------------------------------

def _seed_with(monkeypatch, password):
    Session = make_engine_and_session()
    monkeypatch.setattr(main_module, "SessionLocal", Session)
    monkeypatch.setattr(main_module.settings, "FIRST_SUPERUSER_PASSWORD", password)
    main_module.seed_first_superuser()
    return Session()


def test_seeding_refuses_a_weak_admin_password(monkeypatch):
    with pytest.raises(RuntimeError, match="FIRST_SUPERUSER_PASSWORD"):
        _seed_with(monkeypatch, "admin")


def test_seeding_creates_the_admin_with_a_strong_password(monkeypatch):
    db = _seed_with(monkeypatch, "Vq7-plum-harbor-92")
    assert db.query(User).count() == 1 and db.query(User).one().is_superuser


def test_seeding_leaves_an_existing_database_alone(monkeypatch):
    Session = make_engine_and_session()
    make_user(Session(), "someone")
    monkeypatch.setattr(main_module, "SessionLocal", Session)
    monkeypatch.setattr(main_module.settings, "FIRST_SUPERUSER_PASSWORD", "admin")
    main_module.seed_first_superuser()  # would raise if it tried to create an admin
    assert Session().query(User).count() == 1


# --- login lockout --------------------------------------------------------

def _login(username="ghost", password="wrong-password"):
    return client.post("/api/auth/login", data={"username": username, "password": password})


def test_repeated_failed_logins_are_locked_out(unauthenticated):
    assert [_login().status_code for _ in range(5)] == [401] * 5
    locked = _login()
    assert locked.status_code == 429 and "Retry-After" in locked.headers


def test_a_lockout_is_per_account(unauthenticated):
    for _ in range(5):
        _login("ghost")
    assert _login("someone-else").status_code == 401


def test_the_lockout_expires(unauthenticated, monkeypatch):
    for _ in range(5):
        _login()
    later = login_guard.time.monotonic() + login_guard.WINDOW_SECONDS + 5
    monkeypatch.setattr(login_guard.time, "monotonic", lambda: later)
    assert _login().status_code == 401


# --- fuel validation ------------------------------------------------------

FUEL = {"ship_type": "Tanker (VLCC)", "route_id": "x", "fuel_type": "LNG",
        "weather_conditions": "Calm", "distance": 5000, "month_num": 6}


@pytest.mark.parametrize("change", [
    {"month_num": 99}, {"month_num": 0}, {"distance": -5}, {"distance": 0}, {"distance": 1e9},
    {"ship_type": "Submarine"}, {"fuel_type": "Coal"}, {"weather_conditions": "Foggy"}, {"price_hub": "ZZZZZ"},
])
def test_bad_fuel_inputs_are_a_422(change):
    assert client.post("/api/fuel/predict", json={**FUEL, **change}).status_code == 422


def test_infinite_distance_is_a_422_not_a_database_error():
    response = client.post("/api/fuel/predict", content='{"ship_type":"Tanker (VLCC)","route_id":"x","fuel_type":"LNG",'
                           '"weather_conditions":"Calm","distance":1e999,"month_num":6}',
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_a_valid_fuel_request_still_works():
    assert client.post("/api/fuel/predict", json=FUEL).json()["status"] in ("COMPLETED", "PENDING_APPROVAL")


# --- route validation -----------------------------------------------------

def test_the_same_origin_and_destination_is_a_clear_422():
    response = client.get("/api/route/optimize", params={"origin": "Shanghai", "destination": "shanghai"})
    assert response.status_code == 422 and "different" in response.json()["detail"]


@pytest.mark.parametrize("weights", [
    "risk:-1,cost:1,delay:1,emissions:1", "risk:0,cost:0,delay:0,emissions:0",
    "risk:nan,cost:1,delay:1,emissions:1", "speed:1,risk:1", "risk:inf,cost:1",
])
def test_bad_route_weights_are_a_422(weights):
    response = client.get("/api/route/optimize", params={"origin": "Shanghai", "destination": "Rotterdam", "weights": weights})
    assert response.status_code == 422


def test_good_weights_still_work():
    response = client.get("/api/route/optimize", params={
        "origin": "Shanghai", "destination": "Rotterdam", "weights": "risk:0.5,cost:0.5,delay:0,emissions:0"})
    assert response.status_code == 200


# --- agent status ---------------------------------------------------------

def test_an_agent_status_must_be_a_known_one():
    response = client.post("/api/governance/agents/fuel-agent/status", params={"status": "BANANA"})
    assert response.status_code == 422 and "QUARANTINED" in response.json()["detail"]
