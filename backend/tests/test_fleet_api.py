"""Fleet API: registration and validation, per-account isolation, capacity,
role visibility, live-position merging and removal. Runs on an isolated
in-memory database with the real role checks (conftest's blanket admin
override is dropped)."""

import pytest
from fastapi.testclient import TestClient

from app.agents.fleet.tracker import fleet_tracker
from app.api.dependencies.auth import get_current_active_superuser, get_current_active_user
from app.api.dependencies.database import get_db
from app.core.config import settings
from app.core.constants import UserRole
from app.main import app
from app.models.fleet import VesselAlert

from tests.fleet_support import (
    IMO_A, IMO_B, MMSI_A, MMSI_B, MMSI_C, make_engine_and_session, make_user, make_vessel,
    position_msg, reset_tracker, static_msg,
)

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist

VESSEL = {"name": "ever given", "mmsi": MMSI_A, "imo": IMO_B, "vessel_type": "container_ship"}


@pytest.fixture
def db():
    Session = make_engine_and_session()
    session = Session()

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    reset_tracker()
    yield session
    app.dependency_overrides.clear()
    reset_tracker()
    session.close()


def act_as(user):
    app.dependency_overrides.pop(get_current_active_superuser, None)
    app.dependency_overrides[get_current_active_user] = lambda: user


def register(body=None, **overrides):
    return client.post("/api/fleet/vessels", json={**(body or VESSEL), **overrides})


# --- registration --------------------------------------------------------

def test_registering_a_vessel_normalizes_it_and_starts_tracking_it(db):
    act_as(make_user(db, "olive"))

    response = register()

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "EVER GIVEN" and body["imo"] == IMO_B and body["mmsi"] == MMSI_A
    assert body["status"] == "awaiting_signal" and body["position"] is None
    assert body["identity"]["verification"] == "unverified"
    assert body["is_mine"] is True and body["owner"] == "olive"
    assert fleet_tracker.watched() == {int(MMSI_A)}


def test_imo_may_be_typed_with_its_prefix(db):
    act_as(make_user(db, "olive"))
    assert register(imo="IMO 9811000").json()["imo"] == IMO_B


def test_imo_and_call_sign_are_optional(db):
    act_as(make_user(db, "olive"))
    response = client.post("/api/fleet/vessels", json={"name": "Coastal Star", "mmsi": MMSI_C})
    assert response.status_code == 201 and response.json()["imo"] is None
    assert response.json()["vessel_type"] == "other"


@pytest.mark.parametrize("bad", [
    {"mmsi": "12345"},
    {"mmsi": "970123456"},
    {"imo": "9811001"},          # wrong check digit
    {"imo": "12345"},
    {"vessel_type": "submarine"},
    {"name": "   "},
])
def test_invalid_identity_is_rejected(db, bad):
    act_as(make_user(db, "olive"))
    assert register(**bad).status_code == 422


def test_the_same_mmsi_or_imo_cannot_be_registered_twice(db):
    act_as(make_user(db, "olive"))
    assert register().status_code == 201
    assert register().status_code == 409
    assert register(mmsi=MMSI_B).status_code == 409  # same IMO, different MMSI


def test_a_vessel_registered_by_someone_else_is_also_a_conflict(db):
    act_as(make_user(db, "olive"))
    register()
    act_as(make_user(db, "omar"))
    response = register()
    assert response.status_code == 409
    assert "olive" not in response.text  # never reveals who holds it


def test_registration_stops_at_the_ais_capacity(db, monkeypatch):
    monkeypatch.setattr(settings, "FLEET_MAX_TRACKED_VESSELS", 1)
    act_as(make_user(db, "olive"))
    assert register().status_code == 201
    over = register(name="Second", mmsi=MMSI_C, imo=IMO_A)
    assert over.status_code == 409 and "capacity" in over.json()["detail"]


def test_registration_needs_a_signed_in_user():
    app.dependency_overrides.clear()
    assert client.post("/api/fleet/vessels", json=VESSEL).status_code == 401


# --- isolation and roles -------------------------------------------------

def test_an_operator_sees_only_their_own_fleet(db):
    olive, omar = make_user(db, "olive"), make_user(db, "omar")
    make_vessel(db, olive, "OLIVE ONE", MMSI_A)
    make_vessel(db, omar, "OMAR ONE", MMSI_B)

    act_as(olive)
    names = [v["name"] for v in client.get("/api/fleet/vessels").json()["vessels"]]

    assert names == ["OLIVE ONE"]


def test_another_operators_vessel_is_not_found_rather_than_forbidden(db):
    olive, omar = make_user(db, "olive"), make_user(db, "omar")
    theirs = make_vessel(db, olive, "OLIVE ONE", MMSI_A)

    act_as(omar)
    assert client.get(f"/api/fleet/vessels/{theirs.id}").status_code == 404
    assert client.patch(f"/api/fleet/vessels/{theirs.id}", json={"name": "HIJACK"}).status_code == 404
    assert client.delete(f"/api/fleet/vessels/{theirs.id}").status_code == 404


def test_only_supervisors_and_admins_can_view_every_fleet(db):
    olive = make_user(db, "olive")
    make_vessel(db, olive, "OLIVE ONE", MMSI_A)

    act_as(olive)
    assert client.get("/api/fleet/vessels?scope=all").status_code == 403
    assert client.get("/api/fleet/alerts?scope=all").status_code == 403

    act_as(make_user(db, "sam", UserRole.SUPERVISOR))
    everything = client.get("/api/fleet/vessels?scope=all").json()["vessels"]
    assert [(v["name"], v["owner"], v["is_mine"]) for v in everything] == [("OLIVE ONE", "olive", False)]


def test_a_supervisor_can_read_but_not_change_another_fleet(db):
    olive = make_user(db, "olive")
    theirs = make_vessel(db, olive, "OLIVE ONE", MMSI_A)

    act_as(make_user(db, "sam", UserRole.SUPERVISOR))
    assert client.get(f"/api/fleet/vessels/{theirs.id}").status_code == 200
    assert client.patch(f"/api/fleet/vessels/{theirs.id}", json={"name": "X"}).status_code == 403
    assert client.delete(f"/api/fleet/vessels/{theirs.id}").status_code == 403


def test_an_admin_can_change_and_remove_any_vessel(db):
    olive = make_user(db, "olive")
    theirs = make_vessel(db, olive, "OLIVE ONE", MMSI_A)

    act_as(make_user(db, "root", UserRole.ADMIN))
    assert client.patch(f"/api/fleet/vessels/{theirs.id}", json={"name": "renamed"}).json()["name"] == "RENAMED"
    assert client.delete(f"/api/fleet/vessels/{theirs.id}").status_code == 204


# --- live data -----------------------------------------------------------

def test_the_list_shows_the_live_position_and_verifies_identity_from_ais(db):
    act_as(make_user(db, "olive"))
    register()
    fleet_tracker._handle_message(position_msg(MMSI_A, 36.0, -5.6, sog=13.5, cog=88.0, nav=0))
    fleet_tracker._handle_message(static_msg(MMSI_A, "EVER GIVEN", IMO_B))

    body = client.get("/api/fleet/vessels").json()
    vessel = body["vessels"][0]

    assert vessel["position"]["latitude"] == 36.0 and vessel["position"]["live"] is True
    assert vessel["position"]["sog_knots"] == 13.5 and vessel["position"]["nav_status"] == "Under way using engine"
    assert vessel["identity"]["verification"] == "verified"
    assert body["tracking"]["tracked"] == 1 and body["tracking"]["capacity"] == 50


def test_a_wrong_mmsi_shows_up_as_a_mismatch(db):
    act_as(make_user(db, "olive"))
    register()
    fleet_tracker._handle_message(static_msg(MMSI_A, "SOME OTHER SHIP", IMO_A))

    identity = client.get("/api/fleet/vessels").json()["vessels"][0]["identity"]

    assert identity["verification"] == "mismatch" and IMO_A in identity["note"]


def test_the_detail_view_has_a_trail_and_recent_alerts(db):
    olive = make_user(db, "olive")
    act_as(olive)
    vessel_id = register().json()["id"]
    fleet_tracker._handle_message(position_msg(MMSI_A, 36.0, -5.6))
    fleet_tracker._handle_message(position_msg(MMSI_A, 36.1, -5.5))
    db.add(VesselAlert(vessel_id=vessel_id, owner_id=olive.id, kind="AIS_SILENT", severity="warning", message="quiet"))
    db.commit()

    detail = client.get(f"/api/fleet/vessels/{vessel_id}").json()

    assert [p[:2] for p in detail["trail"]] == [[36.0, -5.6], [36.1, -5.5]]
    assert detail["alerts"][0]["kind"] == "AIS_SILENT" and detail["open_alerts"] == 1


def test_summary_counts_what_the_fleet_is_doing(db):
    olive = make_user(db, "olive")
    make_vessel(db, olive, "A", MMSI_A, status="tracking", risk_score=80, risk_level="high")
    make_vessel(db, olive, "B", MMSI_B, status="awaiting_signal")
    make_vessel(db, olive, "C", MMSI_C, status="no_signal")

    act_as(olive)
    summary = client.get("/api/fleet/vessels").json()["summary"]

    assert summary == {"total": 3, "tracking": 1, "awaiting_signal": 1, "no_signal": 1,
                       "elevated_risk": 1, "open_alerts": 0}


# --- changing and removing ----------------------------------------------

def test_pausing_monitoring_stops_tracking_and_resuming_restores_it(db):
    act_as(make_user(db, "olive"))
    vessel_id = register().json()["id"]
    assert fleet_tracker.watched() == {int(MMSI_A)}

    paused = client.patch(f"/api/fleet/vessels/{vessel_id}", json={"monitoring_enabled": False}).json()
    assert paused["status"] == "paused" and fleet_tracker.watched() == set()

    client.patch(f"/api/fleet/vessels/{vessel_id}", json={"monitoring_enabled": True})
    assert fleet_tracker.watched() == {int(MMSI_A)}


def test_identity_cannot_be_edited_only_descriptive_fields(db):
    act_as(make_user(db, "olive"))
    vessel_id = register().json()["id"]

    updated = client.patch(
        f"/api/fleet/vessels/{vessel_id}",
        json={"name": "new name", "flag": "Panama", "call_sign": "H3RC", "mmsi": MMSI_C, "imo": IMO_A},
    ).json()

    assert updated["name"] == "NEW NAME" and updated["flag"] == "Panama" and updated["call_sign"] == "H3RC"
    assert updated["mmsi"] == MMSI_A and updated["imo"] == IMO_B


def test_removing_a_vessel_stops_tracking_it_and_deletes_its_alerts(db):
    olive = make_user(db, "olive")
    act_as(olive)
    vessel_id = register().json()["id"]
    db.add(VesselAlert(vessel_id=vessel_id, owner_id=olive.id, kind="AIS_SILENT", severity="warning", message="quiet"))
    db.commit()

    assert client.delete(f"/api/fleet/vessels/{vessel_id}").status_code == 204

    assert client.get("/api/fleet/vessels").json()["vessels"] == []
    assert fleet_tracker.watched() == set()
    db.expire_all()
    assert db.query(VesselAlert).count() == 0


def test_alerts_are_scoped_to_their_owner_and_hide_resolved_ones_by_default(db):
    from datetime import datetime
    olive, omar = make_user(db, "olive"), make_user(db, "omar")
    mine = make_vessel(db, olive, "OLIVE ONE", MMSI_A)
    theirs = make_vessel(db, omar, "OMAR ONE", MMSI_B)
    db.add_all([
        VesselAlert(vessel_id=mine.id, owner_id=olive.id, kind="AIS_SILENT", severity="warning", message="open"),
        VesselAlert(vessel_id=mine.id, owner_id=olive.id, kind="STOPPED_AT_SEA", severity="warning",
                    message="done", resolved_at=datetime.utcnow()),
        VesselAlert(vessel_id=theirs.id, owner_id=omar.id, kind="AIS_SILENT", severity="warning", message="not mine"),
    ])
    db.commit()

    act_as(olive)
    assert [a["message"] for a in client.get("/api/fleet/alerts").json()["alerts"]] == ["open"]
    everything = client.get("/api/fleet/alerts?include_resolved=true").json()["alerts"]
    assert sorted(a["message"] for a in everything) == ["done", "open"]
    assert all(a["vessel_name"] == "OLIVE ONE" for a in everything)
